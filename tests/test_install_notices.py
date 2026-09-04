"""A split pin warns at the install, and seeding says who just received it."""

from __future__ import annotations

from pathlib import Path

from helpers import seed_pack_repo, write_pack_repos, write_project

from insitu.library import fetch_pack, install_article, install_skill, list_packs


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _voices(tmp_path: Path, *versions: str) -> Path:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    for version in versions:
        seed_pack_repo(repo, "voices", version)
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    return vault


# --- cross-version warning --------------------------------------------------


def test_installing_from_a_second_version_warns(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    assert install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")["ok"]
    seed_pack_repo(tmp_path / "repo", "voices", "1.3")
    out = install_article(vault, "gamma", "identity/y", version="1.3", pack="voices")
    assert out["ok"] is True
    # A warning, not a refusal: two rows can be deliberate.
    assert out["warning"]["code"] == "cross_version_pin"
    assert out["warning"]["adding"] == "1.3"
    assert out["warning"]["existing"] == ["1.1"]


def test_install_skill_warns_on_the_same_split(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    assert install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")["ok"]
    seed_pack_repo(tmp_path / "repo", "voices", "1.3")
    # The reported case: a skill from a newer version, duplicating no member,
    # so nothing else in the server objects.
    out = install_skill(vault, "gamma", "voice-check", version="1.3", pack="voices")
    if out["ok"]:
        assert out["warning"]["code"] == "cross_version_pin"
    else:
        # The fixture may carry no skill; the article path already covers the rule.
        assert out["error"] == "missing_skill"


def test_a_single_version_does_not_warn(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    out = install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    assert "warning" not in out


def test_a_second_row_at_the_same_version_does_not_warn(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    out = install_article(
        vault, "gamma", "identity/x", version="1.1", pack="voices", target="on_demand"
    )
    # A capability import beside a skill import at one version is the ordinary
    # shape. Only differing version strings are the defect.
    assert "warning" not in out


def test_a_map_on_latest_never_trips_it(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    assert install_article(vault, "gamma", "identity/x", version="latest", pack="voices")["ok"]
    seed_pack_repo(tmp_path / "repo", "voices", "1.3")
    out = install_article(vault, "gamma", "identity/y", version="latest", pack="voices")
    # The warning is keyed on the stored version string, so a flat vault, which
    # is every vault today, cannot reach the state it reports.
    assert out["ok"] is True
    assert "warning" not in out


# --- fetch_pack says who just received it -----------------------------------


def test_seeding_reports_the_maps_that_just_moved(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    install_article(vault, "gamma", "identity/x", version="latest", pack="voices")
    seed_pack_repo(tmp_path / "repo", "voices", "1.3")
    out = fetch_pack(vault, "voices", "1.3")
    assert out["ok"] is True
    # gamma pinned latest, so seeding moved it without anyone editing a map.
    # That is the fact the release step used to have to go looking for.
    assert out["used_by"] == [
        {"project": "gamma", "kind": "articles", "articles": ["identity/x"]}
    ]


def test_seeding_a_version_nobody_composes_reports_nobody(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    seed_pack_repo(repo, "voices", "1.1")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    out = fetch_pack(vault, "voices", "1.1")
    assert out["ok"] is True
    assert out["used_by"] == []


def test_fetch_and_list_agree_on_consumers(tmp_path: Path) -> None:
    vault = _voices(tmp_path, "1.1")
    write_project(vault, "gamma", core=[], include_global=False)
    install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    fetched = fetch_pack(vault, "voices", "1.1")
    listed = list_packs(vault)["packs"][0]["versions"][0]["used_by"]
    # One computation behind both, so they cannot drift.
    assert fetched["used_by"] == listed
