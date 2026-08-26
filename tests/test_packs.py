from __future__ import annotations

from pathlib import Path

import yaml

from helpers import seed_pack_repo, write_pack_repos, write_project, write_stanza

from insitu.catalog import get_project, get_stanza, list_stanzas, where_used
from insitu.library import (
    fetch_pack,
    get_pack,
    install_capability,
    install_stanza,
    list_packs,
    load_pack_repos,
    remove_pack,
    uninstall_capability,
    uninstall_stanza,
)
from insitu.mutate import update_project
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "stanzas").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _with_repo(tmp_path: Path, pack_id: str, version: str) -> tuple[Path, Path]:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    seed_pack_repo(repo, pack_id, version)
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "alpha", core=[], include_global=False)
    write_project(vault, "beta", core=[], include_global=False)
    return vault, repo


def _core_ids(result: dict) -> list[str]:
    return [item["id"] for item in result["core"]]


def _core_bodies(result: dict) -> dict[str, str]:
    return {item["id"]: item["content"] for item in result["core"]}


def test_missing_pack_repos_is_shelf_only(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    assert load_pack_repos(vault) == []
    write_pack_repos(vault, [])
    assert load_pack_repos(vault) == []
    write_project(vault, "alpha", core=[], include_global=False)
    result = install_capability(vault, "alpha", "harbor-kit", "0.1.0")
    assert result["ok"] is False
    assert result["error"] == "version_missing"
    assert not (vault / "library" / "harbor-kit").exists()


def test_install_capability_pulls_and_resolves_role_core(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    result = install_capability(vault, "alpha", "harbor-kit", "0.1.0")
    assert result["ok"] is True
    shelf = vault / "library" / "harbor-kit" / "0.1.0"
    assert (shelf / "stanzas" / "methodology" / "dock-rule.md").is_file()
    assert (shelf / "pack.yaml").is_file()
    assert (shelf / "VERSION").is_file()
    assert not (shelf / "INDEX.md").exists()
    assert not (shelf / "CHANGELOG.md").exists()
    assert not (shelf / "feedback").exists()
    lock = yaml.safe_load((vault / "library" / "lock.yaml").read_text(encoding="utf-8"))
    assert lock["harbor-kit"]["0.1.0"]["source"] == "fixture"
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["imports"] == [{"pack": "harbor-kit", "version": "0.1.0"}]
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["ok"] is True
    assert _core_ids(resolved) == ["methodology/dock-rule"]
    assert "DOCK-0.1.0" in _core_bodies(resolved)["methodology/dock-rule"]
    assert "demo/ignored" not in _core_ids(resolved)


def test_second_project_hits_shelf_without_second_tree(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    first = install_capability(vault, "alpha", "harbor-kit", "0.1.0")
    assert first["ok"] is True
    stamp = (vault / "library" / "harbor-kit" / "0.1.0" / "VERSION").stat().st_mtime_ns
    second = install_capability(vault, "beta", "harbor-kit", "0.1.0")
    assert second["ok"] is True
    assert (vault / "library" / "harbor-kit" / "0.1.0" / "VERSION").stat().st_mtime_ns == stamp
    versions = list((vault / "library" / "harbor-kit").iterdir())
    assert [p.name for p in versions if p.is_dir()] == ["0.1.0"]
    beta = yaml.safe_load(
        (vault / "projects" / "beta" / "map.yaml").read_text(encoding="utf-8")
    )
    assert beta["imports"] == [{"pack": "harbor-kit", "version": "0.1.0"}]


def test_second_project_pulls_newer_version_beside_older(tmp_path: Path) -> None:
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    seed_pack_repo(repo, "harbor-kit", "0.1.1")
    assert install_capability(vault, "beta", "harbor-kit", "0.1.1")["ok"] is True
    assert (vault / "library" / "harbor-kit" / "0.1.0").is_dir()
    assert (vault / "library" / "harbor-kit" / "0.1.1").is_dir()
    assert (vault / "library" / "harbor-kit" / "0.1.1" / "skills" / "demo" / "ignored.md").is_file()
    alpha = resolve_protocol(vault, "alpha")
    beta = resolve_protocol(vault, "beta")
    assert _core_ids(alpha) == ["methodology/dock-rule"]
    assert "DOCK-0.1.0" in _core_bodies(alpha)["methodology/dock-rule"]
    assert _core_ids(beta) == ["methodology/dock-rule", "methodology/harbor-watch"]
    assert "DOCK-0.1.1" in _core_bodies(beta)["methodology/dock-rule"]
    assert "WATCH-0.1.1" in _core_bodies(beta)["methodology/harbor-watch"]


def test_install_stanza_two_versions_compose_only_those_members(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    seed_pack_repo(repo, "voices", "1.1")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "gamma", core=[], include_global=False)
    assert install_stanza(vault, "gamma", "identity/x", version="1.1", pack="voices")["ok"]
    seed_pack_repo(repo, "voices", "1.3")
    assert install_stanza(vault, "gamma", "identity/y", version="1.3", pack="voices")["ok"]
    assert (vault / "library" / "voices" / "1.1").is_dir()
    assert (vault / "library" / "voices" / "1.3").is_dir()
    resolved = resolve_protocol(vault, "gamma")
    assert _core_ids(resolved) == ["identity/x", "identity/y"]
    bodies = _core_bodies(resolved)
    assert "X-1.1" in bodies["identity/x"]
    assert "Y-1.3" in bodies["identity/y"]
    data = yaml.safe_load(
        (vault / "projects" / "gamma" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["imports"] == [
        {"pack": "voices", "version": "1.1", "stanzas": ["identity/x"]},
        {"pack": "voices", "version": "1.3", "stanzas": ["identity/y"]},
    ]


def test_install_capability_latest_stores_latest_and_picks_newest(tmp_path: Path) -> None:
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True
    seed_pack_repo(repo, "harbor-kit", "0.1.1")
    result = install_capability(vault, "alpha", "harbor-kit", "latest")
    assert result["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["imports"] == [{"pack": "harbor-kit", "version": "latest"}]
    resolved = resolve_protocol(vault, "alpha")
    assert "methodology/harbor-watch" in _core_ids(resolved)
    assert "DOCK-0.1.1" in _core_bodies(resolved)["methodology/dock-rule"]


def test_missing_version_is_structured_miss_and_does_not_write_map(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    before = (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    result = install_capability(vault, "alpha", "harbor-kit", "9.9.9")
    assert result["ok"] is False
    assert result["error"] == "version_missing"
    assert result["pack"] == "harbor-kit"
    assert result["version"] == "9.9.9"
    assert "0.1.0" in result["available"]
    assert result["default"] == "0.1.0"
    assert (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8") == before
    assert not (vault / "library" / "harbor-kit" / "9.9.9").exists()


def test_exact_pin_notices_newer_available(tmp_path: Path) -> None:
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    seed_pack_repo(repo, "harbor-kit", "0.1.1")
    assert fetch_pack(vault, "harbor-kit", "0.1.1", repo="fixture")["ok"] is True
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["ok"] is True
    assert _core_ids(resolved) == ["methodology/dock-rule"]
    assert "DOCK-0.1.0" in _core_bodies(resolved)["methodology/dock-rule"]
    notice = resolved["newer_available"]
    assert notice == [
        {"pack": "harbor-kit", "pinned": "0.1.0", "newer": "0.1.1"},
    ]


def test_uninstall_capability_drops_record_keeps_shelf(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    assert install_capability(vault, "beta", "harbor-kit", "0.1.0")["ok"] is True
    gone = uninstall_capability(vault, "alpha", "harbor-kit", "0.1.0")
    assert gone["ok"] is True
    alpha = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert not alpha.get("imports")
    assert (vault / "library" / "harbor-kit" / "0.1.0").is_dir()
    beta = resolve_protocol(vault, "beta")
    assert "methodology/dock-rule" in _core_ids(beta)


def test_validate_reports_unreferenced_version_after_uninstall(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    assert uninstall_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    report = validate(vault)
    assert report["ok"] is True
    unre = report["findings"]["unreferenced_version"]
    assert any(
        item["pack"] == "harbor-kit" and item["version"] == "0.1.0" for item in unre
    )
    fixed = validate(vault, fix=True)
    assert (vault / "library" / "harbor-kit" / "0.1.0").is_dir()
    assert any(
        item["pack"] == "harbor-kit" and item["version"] == "0.1.0"
        for item in fixed["findings"]["unreferenced_version"]
    )


def test_remove_pack_preview_then_confirm(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True
    preview = remove_pack(vault, "harbor-kit", "0.1.0")
    assert preview["ok"] is True
    assert preview["written"] is False
    assert (vault / "library" / "harbor-kit" / "0.1.0").is_dir()
    confirmed = remove_pack(
        vault, "harbor-kit", "0.1.0", confirm=True, expected=preview["expected"]
    )
    assert confirmed["ok"] is True
    assert confirmed["written"] is True
    assert not (vault / "library" / "harbor-kit" / "0.1.0").exists()


def test_remove_pack_drops_map_records_on_confirm(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    preview = remove_pack(vault, "harbor-kit", "0.1.0")
    assert "alpha" in preview["expected"]["projects"]
    confirmed = remove_pack(
        vault, "harbor-kit", "0.1.0", confirm=True, expected=preview["expected"]
    )
    assert confirmed["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert not data.get("imports")
    assert not (vault / "library" / "harbor-kit" / "0.1.0").exists()


def test_fetch_pack_seeds_without_map_change(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    before = (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    result = fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")
    assert result["ok"] is True
    assert (vault / "library" / "harbor-kit" / "0.1.0").is_dir()
    assert (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8") == before
    listed = list_packs(vault)
    assert listed["ok"] is True
    kit = next(p for p in listed["packs"] if p["id"] == "harbor-kit")
    versions = {row["version"] for row in kit["versions"]}
    assert "0.1.0" in versions
    assert any(row.get("unreferenced") for row in kit["versions"] if row["version"] == "0.1.0")


def test_get_stanza_and_list_stanzas_honor_library(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    native_miss = get_stanza(vault, "methodology/dock-rule")
    assert native_miss["ok"] is False
    found = get_stanza(vault, "methodology/dock-rule", project="alpha")
    assert found["ok"] is True
    assert "DOCK-0.1.0" in found["content"]
    assert found["origin"] == "library/harbor-kit@0.1.0"
    rows = list_stanzas(vault)
    origins = {
        (row["id"], row["origin"])
        for row in rows["stanzas"]
        if row["id"] == "methodology/dock-rule"
    }
    assert ("methodology/dock-rule", "library/harbor-kit@0.1.0") in origins
    used = where_used(vault, "methodology/dock-rule")
    assert any(
        item.get("project") == "alpha" and "import:harbor-kit@0.1.0" in item.get("lists", [])
        for item in used["used_by"]
    )


def test_validate_broken_pin_and_duplicate_import_ids(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    write_project(
        vault,
        "broken",
        core=[],
        include_global=False,
        imports=[{"pack": "harbor-kit", "version": "0.1.0"}],
    )
    report = validate(vault)
    assert report["ok"] is False
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "broken_pin" in kinds

    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    write_project(
        vault,
        "duped",
        core=[],
        include_global=False,
        imports=[
            {"pack": "harbor-kit", "version": "0.1.0", "stanzas": ["methodology/dock-rule"]},
            {"pack": "harbor-kit", "version": "0.1.0", "stanzas": ["methodology/dock-rule"]},
        ],
    )
    duped = validate(vault)
    assert duped["ok"] is False
    assert any(issue["kind"] == "duplicate_import_stanza" for issue in duped["issues"])


def test_update_project_does_not_pull(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    write_stanza(vault, "interaction/local", "LOCAL")
    result = update_project(vault, "alpha", add_core=["interaction/local"])
    assert result["ok"] is True
    assert not (vault / "library").exists() or not (vault / "library" / "harbor-kit").exists()


def test_get_pack_and_get_project_surface_imports(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    pack = get_pack(vault, "harbor-kit")
    assert pack["ok"] is True
    assert pack["id"] == "harbor-kit"
    assert "0.1.0" in {row["version"] for row in pack["versions"]}
    project = get_project(vault, "alpha")
    assert project["imports"] == [{"pack": "harbor-kit", "version": "0.1.0"}]


def test_load_vault_reads_imports(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    write_project(
        vault,
        "alpha",
        core=[],
        include_global=False,
        imports=[{"pack": "harbor-kit", "version": "0.1.0"}],
    )
    loaded = load_vault(vault)
    assert loaded.projects["alpha"].imports[0].pack == "harbor-kit"
    assert loaded.projects["alpha"].imports[0].version == "0.1.0"
    assert loaded.projects["alpha"].imports[0].stanzas is None
