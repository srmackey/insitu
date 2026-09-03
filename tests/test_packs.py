from __future__ import annotations

from pathlib import Path

import yaml

from helpers import seed_pack_repo, write_pack_repos, write_project, write_article

from insitu.catalog import get_project, get_article, list_articles, where_used
from insitu.library import (
    fetch_pack,
    get_pack,
    install_capability,
    install_article,
    list_packs,
    load_pack_repos,
    pull_pack_version,
    remove_pack,
    uninstall_capability,
    uninstall_article,
)
from insitu.mutate import update_project
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
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
    assert (shelf / "articles" / "methodology" / "dock-rule.md").is_file()
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


def test_install_article_two_versions_compose_only_those_members(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    seed_pack_repo(repo, "voices", "1.1")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "gamma", core=[], include_global=False)
    assert install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")["ok"]
    seed_pack_repo(repo, "voices", "1.3")
    assert install_article(vault, "gamma", "identity/y", version="1.3", pack="voices")["ok"]
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
        {"pack": "voices", "version": "1.1", "articles": ["identity/x"]},
        {"pack": "voices", "version": "1.3", "articles": ["identity/y"]},
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


def test_get_article_and_list_articles_honor_library(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    native_miss = get_article(vault, "methodology/dock-rule")
    assert native_miss["ok"] is False
    found = get_article(vault, "methodology/dock-rule", project="alpha")
    assert found["ok"] is True
    assert "DOCK-0.1.0" in found["content"]
    assert found["origin"] == "library/harbor-kit@0.1.0"
    rows = list_articles(vault)
    origins = {
        (row["id"], row["origin"])
        for row in rows["articles"]
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
            {"pack": "harbor-kit", "version": "0.1.0", "articles": ["methodology/dock-rule"]},
            {"pack": "harbor-kit", "version": "0.1.0", "articles": ["methodology/dock-rule"]},
        ],
    )
    duped = validate(vault)
    assert duped["ok"] is False
    assert any(issue["kind"] == "duplicate_import_article" for issue in duped["issues"])


def test_update_project_does_not_pull(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    write_article(vault, "interaction/local", "LOCAL")
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
    assert loaded.projects["alpha"].imports[0].articles is None


def test_confirmed_refresh_from_a_repo_actually_writes(tmp_path: Path) -> None:
    """The 2026-08-28 miss: confirmed refresh reported ok and wrote nothing.

    `pull_pack_version` short-circuited on `existing is not None and path is
    None`, so the preview and confirm gate above it were dead on the repo
    path. Only an explicit `path` defeated the guard.
    """
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True

    source = repo / "harbor-kit" / "pack.yaml"
    shelf = vault / "library" / "harbor-kit" / "0.1.0" / "pack.yaml"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n# edited in place\n", encoding="utf-8"
    )
    assert shelf.read_text(encoding="utf-8") != source.read_text(encoding="utf-8")

    plan = fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")
    assert plan == {
        "ok": True,
        "written": False,
        "expected": {"pack": "harbor-kit", "version": "0.1.0", "refresh": True},
    }

    done = fetch_pack(
        vault,
        "harbor-kit",
        "0.1.0",
        repo="fixture",
        confirm=True,
        expected=plan["expected"],
    )
    assert done["ok"] is True
    assert done["refreshed"] is True
    assert shelf.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_unconfirmed_fetch_of_an_unchanged_pack_stays_a_no_op(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True
    again = fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")
    assert again["ok"] is True
    assert again["refreshed"] is False


def test_pull_pack_version_still_short_circuits_without_refresh(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True
    result = pull_pack_version(vault, "harbor-kit", "0.1.0", repo="fixture")
    assert result["ok"] is True
    assert result["pulled"] is False
    assert result["reason"] == "already_present"


# --- on-demand at the article grain ---------------------------------------
# Before this, `install_article` had no target and `record_member_ids`
# short-circuited `on_demand` to empty for a non-capability record. A theme
# pack, the one kind meant to be installed article by article, was the one kind
# that could never ship an on-demand member.


def _on_demand_ids(result: dict) -> list[str]:
    return [item["id"] for item in result["on_demand"]]


def test_install_article_can_target_on_demand(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    result = install_article(
        vault, "alpha", "methodology/dock-rule", "0.1.0", target="on_demand"
    )
    assert result["ok"] is True
    assert result["target"] == "on_demand"

    resolved = resolve_protocol(vault, "alpha")
    assert _core_ids(resolved) == []
    assert _on_demand_ids(resolved) == ["methodology/dock-rule"]


def test_install_article_defaults_to_core(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    assert install_article(vault, "alpha", "methodology/dock-rule", "0.1.0")["ok"] is True
    resolved = resolve_protocol(vault, "alpha")
    assert _core_ids(resolved) == ["methodology/dock-rule"]
    assert _on_demand_ids(resolved) == []


def test_install_article_rejects_an_unknown_target(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    result = install_article(
        vault, "alpha", "methodology/dock-rule", "0.1.0", target="whenever"
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_target"
    assert result["value"] == "whenever"


def test_one_pack_version_can_split_across_core_and_on_demand(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.1")
    assert install_article(vault, "alpha", "methodology/dock-rule", "0.1.1")["ok"] is True
    assert install_article(
        vault, "alpha", "methodology/harbor-watch", "0.1.1", target="on_demand"
    )["ok"] is True

    data = yaml.safe_load((vault / "projects" / "alpha" / "map.yaml").read_text("utf-8"))
    assert len(data["imports"]) == 1
    record = data["imports"][0]
    assert record["articles"] == ["methodology/dock-rule"]
    assert record["on_demand"] == ["methodology/harbor-watch"]

    resolved = resolve_protocol(vault, "alpha")
    assert _core_ids(resolved) == ["methodology/dock-rule"]
    assert _on_demand_ids(resolved) == ["methodology/harbor-watch"]


def test_on_demand_import_survives_a_reload(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    install_article(vault, "alpha", "methodology/dock-rule", "0.1.0", target="on_demand")
    reloaded = load_vault(vault)
    record = reloaded.projects["alpha"].imports[0]
    assert record.on_demand == ["methodology/dock-rule"]
    assert record.articles is None
    assert record.is_capability() is False


def test_uninstall_article_drops_an_on_demand_member(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.1")
    install_article(vault, "alpha", "methodology/dock-rule", "0.1.1")
    install_article(
        vault, "alpha", "methodology/harbor-watch", "0.1.1", target="on_demand"
    )
    result = uninstall_article(
        vault, "alpha", "methodology/harbor-watch", "harbor-kit", "0.1.1"
    )
    assert result["ok"] is True
    resolved = resolve_protocol(vault, "alpha")
    assert _core_ids(resolved) == ["methodology/dock-rule"]
    assert _on_demand_ids(resolved) == []


def test_uninstall_the_last_on_demand_member_drops_the_record(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    install_article(vault, "alpha", "methodology/dock-rule", "0.1.0", target="on_demand")
    assert uninstall_article(
        vault, "alpha", "methodology/dock-rule", "harbor-kit", "0.1.0"
    )["ok"] is True
    data = yaml.safe_load((vault / "projects" / "alpha" / "map.yaml").read_text("utf-8"))
    assert "imports" not in data


def test_an_on_demand_only_import_still_validates(tmp_path: Path) -> None:
    vault, _repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    install_article(vault, "alpha", "methodology/dock-rule", "0.1.0", target="on_demand")
    report = validate(vault)
    assert report["ok"] is True
    assert [i for i in report["issues"] if i["kind"] == "missing_article"] == []


def _make_theme(repo: Path, pack_id: str) -> None:
    path = repo / pack_id / "pack.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["kind"] = "theme"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_theme_pack_refuses_whole_capability_install(tmp_path: Path) -> None:
    """A theme pack is a menu, so subscribing to the whole thing is a request it
    cannot answer. The refusal names the members instead of relying on an empty
    role file to make the install silently do nothing."""
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    _make_theme(repo, "harbor-kit")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True

    result = install_capability(vault, "alpha", "harbor-kit", "0.1.0")
    assert result["ok"] is False
    assert result["error"] == "theme_pack_not_capability"
    assert result["members"] == ["methodology/dock-rule"]
    assert result["skills"] == ["close-hatch"]

    alpha = get_project(vault, "alpha")
    assert alpha["imports"] == []


def test_theme_pack_still_installs_one_member(tmp_path: Path) -> None:
    vault, repo = _with_repo(tmp_path, "harbor-kit", "0.1.0")
    _make_theme(repo, "harbor-kit")
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True

    result = install_article(vault, "alpha", "methodology/dock-rule", "0.1.0", pack="harbor-kit")
    assert result["ok"] is True
    assert _core_ids(resolve_protocol(vault, "alpha")) == ["methodology/dock-rule"]
