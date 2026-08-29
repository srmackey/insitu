from __future__ import annotations

from pathlib import Path

from helpers import write_project, write_stanza

from insitu.catalog import (
    get_project,
    get_stanza,
    list_on_demand,
    list_projects,
    list_stanzas,
    where_used,
)


def _seed(vault: Path) -> None:
    write_stanza(
        vault,
        "interaction/summary-first",
        "GLOBAL-ONLY-BODY",
        title="Summary first",
        description="Global form",
        tags=["interaction", "core"],
    )
    write_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        "P-BODY",
        title="How I work with AI",
        description="Project prefs",
        tags=["interaction"],
    )
    write_stanza(
        vault,
        "methodology/small-diffs",
        "AVAIL",
        title="Small diffs",
        description="Keep changes small",
        tags=["methodology"],
    )
    write_project(vault, "_global", core=["interaction/summary-first"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai"],
        available=["methodology/small-diffs"],
        repo="river-ledger",
        name="River Ledger",
        aka=["rl"],
        notes="Fictional ledger notes.\n",
    )


def test_list_stanzas_ignores_prov_and_supports_filters(vault: Path) -> None:
    _seed(vault)
    (vault / "stanzas" / "interaction" / "summary-first.prov.md").write_text(
        "# why\n", encoding="utf-8"
    )
    all_rows = list_stanzas(vault)
    assert all_rows["ok"] is True
    ids = {row["id"] for row in all_rows["stanzas"]}
    assert ids == {
        "interaction/summary-first",
        "interaction/how-i-work-with-ai",
        "methodology/small-diffs",
    }
    assert all("content" not in row for row in all_rows["stanzas"])
    assert all("estimated_tokens" in row for row in all_rows["stanzas"])

    prefixed = list_stanzas(vault, prefix="interaction")
    assert {row["id"] for row in prefixed["stanzas"]} == {
        "interaction/summary-first",
        "interaction/how-i-work-with-ai",
    }

    tagged = list_stanzas(vault, tag="methodology")
    assert [row["id"] for row in tagged["stanzas"]] == ["methodology/small-diffs"]


def test_get_stanza_returns_content_and_size(vault: Path) -> None:
    _seed(vault)
    result = get_stanza(vault, "interaction/how-i-work-with-ai")
    assert result["ok"] is True
    assert result["id"] == "interaction/how-i-work-with-ai"
    assert result["content"] == "P-BODY"
    assert result["estimated_tokens"] == len("P-BODY") // 4
    assert "estimate" in result["token_estimate_note"].lower()


def test_get_project_size_without_protocol_body(vault: Path) -> None:
    _seed(vault)
    result = get_project(vault, "river-ledger")
    assert result["ok"] is True
    assert result["project"] == "river-ledger"
    assert result["repo"] == "river-ledger"
    assert result["name"] == "River Ledger"
    assert result["aka"] == ["rl"]
    assert result["notes"] == "Fictional ledger notes.\n"
    assert result["core"] == ["interaction/how-i-work-with-ai"]
    assert "content" not in result
    assert result["size"]["stanza_count"] == 2
    dumped = str(result)
    assert "P-BODY" not in dumped
    assert "GLOBAL-ONLY-BODY" not in dumped


def test_list_projects_includes_global_labels_and_size(vault: Path) -> None:
    _seed(vault)
    result = list_projects(vault)
    assert result["ok"] is True
    by_key = {row["project"]: row for row in result["projects"]}
    assert "_global" in by_key
    assert "river-ledger" in by_key
    river = by_key["river-ledger"]
    assert river["repo"] == "river-ledger"
    assert river["name"] == "River Ledger"
    assert river["aka"] == ["rl"]
    assert "stanza_count" in river["size"]
    assert "estimated_tokens" in river["size"]


def test_list_on_demand_is_non_core_index(vault: Path) -> None:
    _seed(vault)
    result = list_on_demand(vault, "river-ledger")
    assert result["ok"] is True
    assert [row["id"] for row in result["on_demand"]] == ["methodology/small-diffs"]
    assert "content" not in result["on_demand"][0]
    assert result["on_demand"][0]["title"] == "Small diffs"


def test_where_used_lists_core_and_available_refs(vault: Path) -> None:
    _seed(vault)
    used_global = where_used(vault, "interaction/summary-first")
    assert used_global["ok"] is True
    assert used_global["used_by"] == [{"project": "_global", "lists": ["core"]}]

    used_avail = where_used(vault, "methodology/small-diffs")
    assert used_avail["used_by"] == [{"project": "river-ledger", "lists": ["on_demand"]}]


def test_list_and_get_reject_path_escape(vault: Path) -> None:
    bad = get_stanza(vault, "../secret")
    assert bad["ok"] is False
    assert bad["error"] == "invalid_identity"

    listed = list_stanzas(vault, prefix="..")
    assert listed["ok"] is False
    assert listed["error"] == "invalid_identity"
