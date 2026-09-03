from __future__ import annotations

from pathlib import Path

import yaml

from helpers import write_project, write_article

from insitu.resolve import resolve_protocol
from insitu.validate import validate


def test_validate_is_read_only_until_fix(vault: Path) -> None:
    write_article(vault, "interaction/shared", "S")
    write_article(vault, "interaction/local", "L")
    write_project(vault, "_global", core=["interaction/shared"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/shared", "interaction/local", "interaction/local"],
    )
    map_path = vault / "projects" / "river-ledger" / "map.yaml"
    before = map_path.read_bytes()

    report = validate(vault, fix=False)
    assert report["ok"] is False
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "duplicate" in kinds
    assert map_path.read_bytes() == before

    fixed = validate(vault, fix=True)
    assert any(item.get("kind") == "duplicate" for item in fixed.get("fixed", []))
    after = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    # first-wins: drop the in-list repeat and the copy already in _global.core
    assert after["core"] == ["interaction/local"]
    assert before != map_path.read_bytes()


def test_validate_reports_missing_ref_id_mismatch_and_frontmatter(vault: Path) -> None:
    write_article(
        vault,
        "interaction/how-i-work-with-ai",
        "P",
        title=None,
        description="desc",
        extra_fm={"id": "wrong/id"},
        include_id=False,
    )
    # rewrite so title is missing and id mismatches
    path = vault / "articles" / "interaction" / "how-i-work-with-ai.md"
    path.write_text(
        "---\nid: wrong/id\ndescription: desc\n---\n\nP\n",
        encoding="utf-8",
    )
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai", "interaction/missing-piece"],
    )
    report = validate(vault, fix=False)
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "missing_article" in kinds
    assert "id_mismatch" in kinds
    assert "missing_frontmatter" in kinds
    missing = next(i for i in report["issues"] if i["kind"] == "missing_article")
    assert missing["id"] == "interaction/missing-piece"


def test_validate_fix_does_not_strip_core_when_include_global_false(vault: Path) -> None:
    write_article(vault, "interaction/shared", "SHARED-BODY")
    write_article(vault, "interaction/local", "LOCAL-BODY")
    write_project(vault, "_global", core=["interaction/shared"])
    write_project(
        vault,
        "harbor-notes",
        core=["interaction/shared", "interaction/local"],
        include_global=False,
    )
    map_path = vault / "projects" / "harbor-notes" / "map.yaml"
    before = map_path.read_bytes()

    resolved = resolve_protocol(vault, "harbor-notes")
    assert resolved["ok"] is True
    assert [item["id"] for item in resolved["core"]] == [
        "interaction/shared",
        "interaction/local",
    ]

    report = validate(vault, fix=False)
    overlap = [
        issue
        for issue in report["issues"]
        if issue.get("kind") == "duplicate"
        and issue.get("project") == "harbor-notes"
        and issue.get("id") == "interaction/shared"
    ]
    assert overlap == []

    fixed = validate(vault, fix=True)
    assert map_path.read_bytes() == before
    assert fixed["fixed"] == []
    after = resolve_protocol(vault, "harbor-notes")
    assert [item["id"] for item in after["core"]] == [
        "interaction/shared",
        "interaction/local",
    ]
    assert "SHARED-BODY" in after["core"][0]["content"]
