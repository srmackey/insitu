from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from helpers import write_project, write_role, write_article

from insitu.catalog import (
    get_project,
    get_role,
    list_roles,
    list_articles,
    where_used,
)
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _seed_composed(vault: Path) -> None:
    write_article(
        vault,
        "interaction/voice",
        "VOICE-BODY",
        title="Voice",
        description="Global voice pack",
        extra_fm={"roles": ["voice"]},
    )
    write_article(
        vault,
        "interaction/summary-first",
        "GLOBAL-CORE-BODY",
        title="Summary first",
        description="Global form",
    )
    write_article(
        vault,
        "methodology/clerk-intake",
        "CLERK-CORE-BODY",
        title="Clerk intake",
        description="Role core article",
        extra_fm={"roles": ["clerk"]},
    )
    write_article(
        vault,
        "methodology/clerk-reference",
        "CLERK-AVAIL-BODY-MUST-NOT-INLINE",
        title="Clerk reference",
        description="Role available article",
        extra_fm={"roles": ["clerk"]},
    )
    write_article(
        vault,
        "interaction/how-i-work-with-ai",
        "PROJECT-CORE-BODY",
        title="How I work with AI",
        description="Project prefs",
    )
    write_article(
        vault,
        "methodology/small-diffs",
        "PROJECT-AVAIL-BODY",
        title="Small diffs",
        description="Project available",
    )
    write_role(
        vault,
        "voice",
        name="Voice",
        description="Every-project voice",
        core=["interaction/voice"],
    )
    write_role(
        vault,
        "clerk",
        name="Clerk",
        description="Ledger clerk pack",
        core=["methodology/clerk-intake"],
        available=["methodology/clerk-reference"],
    )
    write_project(
        vault,
        "_global",
        roles=["voice"],
        core=["interaction/summary-first"],
    )
    write_project(
        vault,
        "river-ledger",
        roles=["clerk"],
        core=["interaction/how-i-work-with-ai"],
        available=["methodology/small-diffs"],
    )


def test_missing_roles_dir_loads_and_resolves(vault: Path) -> None:
    write_article(vault, "interaction/how-i-work-with-ai", "P")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    loaded = load_vault(vault)
    assert loaded.roles == {}
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["roles"] == []
    assert [item["id"] for item in result["core"]] == ["interaction/how-i-work-with-ai"]


def test_load_roles_and_project_roles(vault: Path) -> None:
    _seed_composed(vault)
    write_role(
        vault,
        "clerk",
        name="Clerk",
        description="Ledger clerk pack",
        core=["methodology/clerk-intake"],
        available=["methodology/clerk-reference"],
        extra={"future_flag": True, "note": "ignored on load"},
    )
    loaded = load_vault(vault)
    assert set(loaded.roles) == {"voice", "clerk"}
    clerk = loaded.roles["clerk"]
    assert clerk.name == "Clerk"
    assert clerk.description == "Ledger clerk pack"
    assert clerk.core == ["methodology/clerk-intake"]
    assert clerk.on_demand == ["methodology/clerk-reference"]
    assert loaded.projects["river-ledger"].roles == ["clerk"]
    assert not hasattr(loaded.articles["methodology/clerk-intake"], "roles")


def test_bad_role_filename_is_skipped(vault: Path) -> None:
    write_article(vault, "interaction/how-i-work-with-ai", "P")
    write_role(vault, "clerk", core=["interaction/how-i-work-with-ai"])
    (vault / "roles" / "Bad_Role.yaml").write_text("core: []\n", encoding="utf-8")
    (vault / "roles" / "_secret.yaml").write_text("core: []\n", encoding="utf-8")
    loaded = load_vault(vault)
    assert set(loaded.roles) == {"clerk"}


def test_compose_order_is_global_composed_then_role_then_map(vault: Path) -> None:
    _seed_composed(vault)
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["roles"] == ["clerk"]
    assert [item["id"] for item in result["core"]] == [
        "interaction/voice",
        "interaction/summary-first",
        "methodology/clerk-intake",
        "interaction/how-i-work-with-ai",
    ]
    bodies = [item["content"] for item in result["core"]]
    assert bodies == [
        "# Voice\n\nVOICE-BODY",
        "# Summary first\n\nGLOBAL-CORE-BODY",
        "# Clerk intake\n\nCLERK-CORE-BODY",
        "# How I work with AI\n\nPROJECT-CORE-BODY",
    ]


def test_first_wins_across_global_role_and_map(vault: Path) -> None:
    write_article(vault, "shared/one", "ONE", extra_fm={"roles": ["pack"]})
    write_article(vault, "shared/two", "TWO", extra_fm={"roles": ["pack"]})
    write_article(vault, "shared/three", "THREE")
    write_role(vault, "pack", core=["shared/one", "shared/two"])
    write_project(vault, "_global", roles=["pack"], core=["shared/one"])
    write_project(
        vault,
        "river-ledger",
        roles=["pack"],
        core=["shared/two", "shared/three"],
    )
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == [
        "shared/one",
        "shared/two",
        "shared/three",
    ]
    assert [item["id"] for item in result["core"]].count("shared/one") == 1


def test_role_available_is_index_not_core(vault: Path) -> None:
    _seed_composed(vault)
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    avail_ids = [item["id"] for item in result["on_demand"]]
    assert avail_ids == ["methodology/clerk-reference", "methodology/small-diffs"]
    core_ids = [item["id"] for item in result["core"]]
    assert "methodology/clerk-reference" not in core_ids
    assert "content" not in result["on_demand"][0]
    assert "CLERK-AVAIL-BODY-MUST-NOT-INLINE" not in str(result)


def test_missing_role_is_hard_error_naming_role(vault: Path) -> None:
    write_article(vault, "interaction/how-i-work-with-ai", "P")
    write_project(
        vault,
        "river-ledger",
        roles=["ghost"],
        core=["interaction/how-i-work-with-ai"],
    )
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is False
    assert result["error"] == "missing_role"
    assert result["id"] == "ghost"


def test_include_global_injects_composed_global_not_raw_core(vault: Path) -> None:
    _seed_composed(vault)
    write_project(
        vault,
        "harbor-notes",
        core=["interaction/how-i-work-with-ai"],
        include_global=True,
    )
    result = resolve_protocol(vault, "harbor-notes")
    assert result["ok"] is True
    assert result["roles"] == []
    assert [item["id"] for item in result["core"]] == [
        "interaction/voice",
        "interaction/summary-first",
        "interaction/how-i-work-with-ai",
    ]


def test_include_global_false_skips_composed_global_roles(vault: Path) -> None:
    _seed_composed(vault)
    write_project(
        vault,
        "harbor-notes",
        roles=["clerk"],
        core=["interaction/how-i-work-with-ai"],
        include_global=False,
    )
    result = resolve_protocol(vault, "harbor-notes")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == [
        "methodology/clerk-intake",
        "interaction/how-i-work-with-ai",
    ]


def test_missing_global_with_project_roles_is_empty_not_error(vault: Path) -> None:
    write_article(
        vault,
        "methodology/clerk-intake",
        "CLERK-CORE-BODY",
        extra_fm={"roles": ["clerk"]},
    )
    write_article(vault, "interaction/how-i-work-with-ai", "P")
    write_role(vault, "clerk", core=["methodology/clerk-intake"])
    write_project(
        vault,
        "river-ledger",
        roles=["clerk"],
        core=["interaction/how-i-work-with-ai"],
    )
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == [
        "methodology/clerk-intake",
        "interaction/how-i-work-with-ai",
    ]


def test_validate_reports_unknown_map_role(vault: Path) -> None:
    write_article(vault, "interaction/how-i-work-with-ai", "P")
    write_project(
        vault,
        "river-ledger",
        roles=["ghost"],
        core=["interaction/how-i-work-with-ai"],
    )
    report = validate(vault, fix=False)
    assert report["ok"] is False
    missing = [i for i in report["issues"] if i["kind"] == "missing_role"]
    assert missing
    assert missing[0]["id"] == "ghost"
    assert missing[0]["project"] == "river-ledger"


def test_validate_reports_missing_article_inside_role(vault: Path) -> None:
    write_article(vault, "methodology/clerk-intake", "C", extra_fm={"roles": ["clerk"]})
    write_role(
        vault,
        "clerk",
        core=["methodology/clerk-intake", "methodology/missing-piece"],
    )
    write_project(vault, "river-ledger", roles=["clerk"])
    report = validate(vault, fix=False)
    assert report["ok"] is False
    missing = [
        i
        for i in report["issues"]
        if i["kind"] == "missing_article" and i["id"] == "methodology/missing-piece"
    ]
    assert missing
    assert missing[0].get("role") == "clerk"


def test_validate_reports_role_file_and_expansion_duplicates(vault: Path) -> None:
    write_article(vault, "shared/one", "ONE", extra_fm={"roles": ["alpha", "beta"]})
    write_article(vault, "shared/two", "TWO", extra_fm={"roles": ["alpha"]})
    write_role(vault, "alpha", core=["shared/one", "shared/one", "shared/two"])
    write_role(vault, "beta", core=["shared/one"])
    write_project(vault, "river-ledger", roles=["alpha", "beta"], core=["shared/two"])
    report = validate(vault, fix=False)
    assert report["ok"] is False
    dupes = [i for i in report["issues"] if i["kind"] == "duplicate"]
    assert any(i.get("role") == "alpha" and i["id"] == "shared/one" for i in dupes)
    assert any(
        i.get("project") == "river-ledger" and i["id"] == "shared/one" for i in dupes
    )
    assert any(
        i.get("project") == "river-ledger" and i["id"] == "shared/two" for i in dupes
    )


def test_stale_roles_key_on_a_article_is_ignored(vault: Path) -> None:
    """The frontmatter mirror is gone. An old vault still carrying the key loads,
    validates clean, and is never rewritten to keep a copy in sync."""
    write_article(
        vault,
        "methodology/clerk-intake",
        "CLERK-CORE-BODY",
        title="Clerk intake",
        description="Role core",
    )
    write_article(
        vault,
        "methodology/orphan-label",
        "ORPHAN-BODY",
        title="Orphan",
        description="Claims a role no role file backs",
        extra_fm={"roles": ["clerk"]},
    )
    orphan_path = vault / "articles" / "methodology" / "orphan-label.md"
    orphan_before = orphan_path.read_bytes()
    role_path = write_role(vault, "clerk", core=["methodology/clerk-intake"])
    role_before = role_path.read_bytes()
    write_project(vault, "river-ledger", roles=["clerk"])

    report = validate(vault, fix=False)
    assert report["ok"] is True
    assert not [i for i in report["issues"] if i["kind"] == "role_membership"]

    fixed = validate(vault, fix=True)
    assert fixed["ok"] is True
    assert fixed.get("fixed", []) == []
    assert orphan_path.read_bytes() == orphan_before
    assert role_path.read_bytes() == role_before
    assert load_vault(vault).roles["clerk"].core == ["methodology/clerk-intake"]


def test_list_roles_and_get_role(vault: Path) -> None:
    _seed_composed(vault)
    listed = list_roles(vault)
    assert listed["ok"] is True
    by_id = {row["id"]: row for row in listed["roles"]}
    assert set(by_id) == {"clerk", "voice"}
    clerk_row = by_id["clerk"]
    assert clerk_row["name"] == "Clerk"
    assert clerk_row["description"] == "Ledger clerk pack"
    assert clerk_row["core_count"] == 1
    assert clerk_row["on_demand_count"] == 1
    assert clerk_row["size"]["article_count"] == 1

    got = get_role(vault, "clerk")
    assert got["ok"] is True
    assert got["id"] == "clerk"
    assert got["name"] == "Clerk"
    assert [item["id"] for item in got["core"]] == ["methodology/clerk-intake"]
    assert got["core"][0]["title"] == "Clerk intake"
    assert "content" not in got["core"][0]
    assert [item["id"] for item in got["on_demand"]] == ["methodology/clerk-reference"]
    assert "river-ledger" in got["projects"]
    assert "_global" not in got["projects"]

    missing = get_role(vault, "ghost")
    assert missing["ok"] is False
    assert missing["error"] == "missing_role"
    assert missing["id"] == "ghost"


def test_list_articles_carries_no_role_membership(vault: Path) -> None:
    """Membership is the role file's fact. get_role answers it from the source."""
    _seed_composed(vault)
    rows = list_articles(vault)["articles"]
    assert rows
    assert all("roles" not in row for row in rows)

    with pytest.raises(TypeError):
        list_articles(vault, role="clerk")

    members = get_role(vault, "clerk")
    assert [item["id"] for item in members["core"]] == ["methodology/clerk-intake"]


def test_where_used_includes_role_files_and_role_expansion(vault: Path) -> None:
    _seed_composed(vault)
    used = where_used(vault, "methodology/clerk-intake")
    assert used["ok"] is True
    assert {"role": "clerk", "lists": ["core"]} in used["used_by"]
    river = next(row for row in used["used_by"] if row.get("project") == "river-ledger")
    assert "role:clerk" in river["lists"]
    assert "core" not in river["lists"]


def test_get_project_exposes_roles(vault: Path) -> None:
    _seed_composed(vault)
    result = get_project(vault, "river-ledger")
    assert result["ok"] is True
    assert result["roles"] == ["clerk"]
    assert "CLERK-CORE-BODY" not in str(result)
