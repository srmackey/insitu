"""Conflict declarations refuse at write and warn at resolve; mentions inform."""

from __future__ import annotations

from pathlib import Path

from helpers import seed_pack_repo, write_article, write_pack_repos, write_project, write_role

from insitu.library import install_article, install_capability
from insitu.mutate import link_article
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _pair(vault: Path) -> None:
    """The motivating case: a rule and its discreet variant."""
    write_article(vault, "methodology/status", "Publish the digest.")
    write_article(
        vault,
        "methodology/status-discreet",
        "Publish summaries and pointers only.",
        extra_fm={"conflicts": ["methodology/status"]},
    )


def test_declaration_is_symmetric_so_one_side_states_it(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    # The discreet variant declares; the plain one says nothing. Either order
    # must refuse, or an author would have to remember to write it twice.
    write_project(vault, "alpha", core=["methodology/status"])
    refused = link_article(vault, "alpha", "methodology/status-discreet")
    assert refused["ok"] is False
    assert refused["error"] == "conflicts_with_composed"
    assert refused["conflicts"][0]["id"] == "methodology/status"

    write_project(vault, "beta", core=["methodology/status-discreet"])
    other_way = link_article(vault, "beta", "methodology/status")
    assert other_way["ok"] is False
    assert other_way["error"] == "conflicts_with_composed"
    assert other_way["conflicts"][0]["declared_by"] == "methodology/status-discreet"


def test_refusal_writes_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    write_project(vault, "alpha", core=["methodology/status"])
    before = (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    link_article(vault, "alpha", "methodology/status-discreet")
    after = (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    assert before == after


def test_conflict_reaching_through_a_role_still_refuses(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    write_role(vault, "clerk", core=["methodology/status"])
    write_project(vault, "alpha", core=[], roles=["clerk"])
    refused = link_article(vault, "alpha", "methodology/status-discreet")
    assert refused["ok"] is False
    assert refused["error"] == "conflicts_with_composed"


def test_on_demand_counts_as_composed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    write_project(vault, "alpha", core=[], on_demand=["methodology/status"])
    refused = link_article(vault, "alpha", "methodology/status-discreet")
    assert refused["ok"] is False


def test_unrelated_article_still_links(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    write_article(vault, "interaction/brief", "Keep it short.")
    write_project(vault, "alpha", core=["methodology/status"])
    assert link_article(vault, "alpha", "interaction/brief")["ok"] is True


def test_resolve_warns_and_still_composes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    # Written straight onto the map, the way an upstream pack bump or a
    # hand-edit arrives. Resolution must not be the thing that fails.
    write_project(
        vault, "alpha", core=["methodology/status", "methodology/status-discreet"]
    )
    out = resolve_protocol(vault, "alpha")
    assert out["ok"] is True
    assert len(out["core"]) == 2
    assert out["conflicts"] == [
        {
            "a": "methodology/status",
            "b": "methodology/status-discreet",
            "declared_by": "methodology/status-discreet",
        }
    ]


def test_clean_protocol_reports_no_conflicts_key(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _pair(vault)
    write_project(vault, "alpha", core=["methodology/status"])
    assert "conflicts" not in resolve_protocol(vault, "alpha")


def test_validate_flags_a_conflict_naming_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    write_article(
        vault,
        "methodology/status",
        "Publish the digest.",
        extra_fm={"conflicts": ["methodology/never-written"]},
    )
    write_project(vault, "alpha", core=["methodology/status"])
    out = validate(vault)
    kinds = [issue["kind"] for issue in out["issues"]]
    assert "missing_conflict" in kinds


def test_conflicts_key_is_optional_and_absent_by_default(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    write_article(vault, "methodology/status", "Publish the digest.")
    loaded = load_vault(vault)
    assert loaded.articles["methodology/status"].conflicts == []


def _voices(tmp_path: Path) -> Path:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    seed_pack_repo(repo, "voices", "1.1")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    return vault


def test_install_refuses_a_conflict_with_what_the_project_composes(
    tmp_path: Path,
) -> None:
    vault = _voices(tmp_path)
    write_article(
        vault,
        "methodology/local",
        "A native rule.",
        extra_fm={"conflicts": ["identity/x"]},
    )
    write_project(vault, "gamma", core=["methodology/local"])
    refused = install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    assert refused["ok"] is False
    assert refused["error"] == "conflicts_with_composed"
    assert refused["pack"] == "voices"
    assert yaml_imports(vault, "gamma") == []


def yaml_imports(vault: Path, key: str) -> list:
    import yaml

    data = yaml.safe_load((vault / "projects" / key / "map.yaml").read_text(encoding="utf-8"))
    return data.get("imports") or []


def test_install_article_names_what_its_text_mentions(tmp_path: Path) -> None:
    vault = _voices(tmp_path)
    write_article(vault, "methodology/companion", "The companion rule.")
    write_project(vault, "gamma", core=[])
    # The installed article's body names a native article this map does not
    # carry. That is the offer the agent makes.
    pack_article = (
        tmp_path / "repo" / "voices" / "articles" / "identity" / "x.md"
    )
    pack_article.write_text(
        pack_article.read_text(encoding="utf-8").replace(
            "X-1.1", "Use with `methodology/companion` when the chair publishes."
        ),
        encoding="utf-8",
    )
    out = install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    assert out["ok"] is True
    assert out["mentions_not_composed"] == ["methodology/companion"]
    assert out["title"] == "Voice X"


def test_mentions_omits_what_is_already_composed(tmp_path: Path) -> None:
    vault = _voices(tmp_path)
    write_article(vault, "methodology/companion", "The companion rule.")
    write_project(vault, "gamma", core=["methodology/companion"])
    pack_article = (
        tmp_path / "repo" / "voices" / "articles" / "identity" / "x.md"
    )
    pack_article.write_text(
        pack_article.read_text(encoding="utf-8").replace(
            "X-1.1", "Use with `methodology/companion`."
        ),
        encoding="utf-8",
    )
    out = install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    assert out["ok"] is True
    assert "mentions_not_composed" not in out


def test_mentions_ignores_an_id_nothing_resolves(tmp_path: Path) -> None:
    vault = _voices(tmp_path)
    write_project(vault, "gamma", core=[])
    pack_article = (
        tmp_path / "repo" / "voices" / "articles" / "identity" / "x.md"
    )
    pack_article.write_text(
        pack_article.read_text(encoding="utf-8").replace(
            "X-1.1", "Pairs with `methodology/does-not-exist`."
        ),
        encoding="utf-8",
    )
    out = install_article(vault, "gamma", "identity/x", version="1.1", pack="voices")
    assert out["ok"] is True
    assert "mentions_not_composed" not in out


def _two_member_pack(repo: Path, *, conflicting: bool) -> None:
    """A capability pack whose two members may or may not declare against each other."""
    root = repo / "quay-kit"
    articles = root / "articles" / "methodology"
    articles.mkdir(parents=True)
    (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (root / "pack.yaml").write_text(
        "id: quay-kit\nname: Quay kit\nkind: capability\nversion: 0.1.0\n"
        "articles:\n  - methodology/tide\n  - methodology/tide-quiet\n"
        "roles:\n  - quay-kit\n",
        encoding="utf-8",
    )
    (root / "roles").mkdir()
    (root / "roles" / "quay-kit.yaml").write_text(
        "name: Quay kit\ndescription: Fictional capability.\n"
        "core:\n  - methodology/tide\n  - methodology/tide-quiet\non_demand: []\n",
        encoding="utf-8",
    )
    (articles / "tide.md").write_text(
        "---\nid: methodology/tide\ntitle: Tide\ndescription: Publish the tide.\n---\n\n# Tide\n\nBody.\n",
        encoding="utf-8",
    )
    declaration = "conflicts: [methodology/tide]\n" if conflicting else ""
    (articles / "tide-quiet.md").write_text(
        "---\nid: methodology/tide-quiet\ntitle: Tide quiet\n"
        f"description: Publish quietly.\n{declaration}---\n\n# Tide quiet\n\nBody.\n",
        encoding="utf-8",
    )


def test_capability_refuses_when_its_own_members_conflict(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _two_member_pack(repo, conflicting=True)
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "gamma", core=[])
    refused = install_capability(vault, "gamma", "quay-kit", version="0.1.0")
    assert refused["ok"] is False
    # No project could compose this pack whole, so the defect is the pack's.
    assert refused["error"] == "pack_conflicts_internally"
    assert refused["conflicts"][0]["a"] == "methodology/tide"


def test_capability_installs_when_its_members_do_not_conflict(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _two_member_pack(repo, conflicting=False)
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "gamma", core=[])
    assert install_capability(vault, "gamma", "quay-kit", version="0.1.0")["ok"] is True


def test_capability_refuses_against_what_the_project_already_composes(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _two_member_pack(repo, conflicting=False)
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_article(
        vault,
        "methodology/local",
        "A native rule.",
        extra_fm={"conflicts": ["methodology/tide"]},
    )
    write_project(vault, "gamma", core=["methodology/local"])
    refused = install_capability(vault, "gamma", "quay-kit", version="0.1.0")
    assert refused["ok"] is False
    assert refused["error"] == "conflicts_with_composed"
    assert refused["id"] == "methodology/tide"
