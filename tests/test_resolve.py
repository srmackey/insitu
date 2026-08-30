from __future__ import annotations

from pathlib import Path

from helpers import write_project, write_stanza

from insitu.resolve import resolve_protocol


def _seed_basic(vault: Path) -> None:
    write_stanza(
        vault,
        "interaction/summary-first",
        "GLOBAL-CORE-BODY",
        title="Summary first",
        description="Global interaction form",
        tags=["interaction", "core"],
    )
    write_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        "PROJECT-CORE-BODY",
        title="How I work with AI",
        description="Project interaction prefs",
        tags=["interaction"],
    )
    write_stanza(
        vault,
        "methodology/small-diffs",
        "AVAILABLE-BODY-MUST-NOT-INLINE",
        title="Small diffs",
        description="Keep changes small",
        tags=["methodology"],
    )
    write_project(
        vault,
        "_global",
        core=["interaction/summary-first"],
    )
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai"],
        available=["methodology/small-diffs"],
        repo="river-ledger",
        name="River Ledger",
        aka=["rl"],
    )


def test_composes_global_then_project(vault: Path) -> None:
    _seed_basic(vault)
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    ids = [item["id"] for item in result["core"]]
    assert ids == [
        "interaction/summary-first",
        "interaction/how-i-work-with-ai",
    ]
    bodies = [item["content"] for item in result["core"]]
    assert bodies == [
        "# Summary first\n\nGLOBAL-CORE-BODY",
        "# How I work with AI\n\nPROJECT-CORE-BODY",
    ]


def test_include_global_false_skips_global_core(vault: Path) -> None:
    _seed_basic(vault)
    write_project(
        vault,
        "harbor-notes",
        core=["interaction/how-i-work-with-ai"],
        include_global=False,
    )
    result = resolve_protocol(vault, "harbor-notes")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == ["interaction/how-i-work-with-ai"]
    assert result["include_global"] is False


def test_missing_global_is_empty_not_error(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == ["interaction/how-i-work-with-ai"]


def test_missing_stanza_is_hard_error_naming_id(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "ok")
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai", "interaction/missing-piece"],
    )
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is False
    assert result["error"] == "missing_stanza"
    assert result["id"] == "interaction/missing-piece"


def test_missing_project_is_structured_miss(vault: Path) -> None:
    result = resolve_protocol(vault, "no-such")
    assert result["ok"] is False
    assert result["error"] == "project_missing"
    assert result["project"] == "no-such"
    assert Path(result["missing_path"]) == vault / "projects" / "no-such"


def test_first_duplicate_wins_and_later_is_dropped(vault: Path) -> None:
    write_stanza(vault, "interaction/shared", "SHARED-BODY")
    write_stanza(vault, "interaction/local", "LOCAL-BODY")
    write_project(vault, "_global", core=["interaction/shared"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/shared", "interaction/local"],
    )
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    ids = [item["id"] for item in result["core"]]
    assert ids == ["interaction/shared", "interaction/local"]
    assert ids.count("interaction/shared") == 1


def test_available_is_index_without_inlined_bodies(vault: Path) -> None:
    _seed_basic(vault)
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert len(result["on_demand"]) == 1
    item = result["on_demand"][0]
    assert item["id"] == "methodology/small-diffs"
    assert item["title"] == "Small diffs"
    assert item["description"] == "Keep changes small"
    assert "content" not in item
    dumped = str(result)
    assert "AVAILABLE-BODY-MUST-NOT-INLINE" not in dumped


def test_size_uses_chars_over_four_and_is_labeled_estimate(vault: Path) -> None:
    body = "abcdefghij"  # 10 chars
    write_stanza(vault, "interaction/how-i-work-with-ai", body)
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    item = result["core"][0]
    # Size measures what composition emits, which carries the heading.
    composed = "# Title\n\n" + body  # 19 chars
    assert item["content"] == composed
    assert item["bytes"] == len(composed.encode("utf-8"))
    assert item["estimated_tokens"] == len(composed) // 4
    assert "estimate" in item["token_estimate_note"].lower()
    assert "chars / 4" in item["token_estimate_note"]
    totals = result["size"]
    assert list(result.keys()).index("size") < list(result.keys()).index("core")
    assert totals["stanza_count"] == 1
    assert totals["bytes"] == item["bytes"]
    assert totals["estimated_tokens"] == item["estimated_tokens"]
    assert "estimate" in totals["token_estimate_note"].lower()


def test_size_totals_sum_each_core_stanza(vault: Path) -> None:
    # Each body composes as "# Title\n\n" + body, so 9 chars of heading each.
    write_stanza(vault, "interaction/one", "abcd")  # 13 chars -> 3 tokens
    write_stanza(vault, "interaction/two", "abcdefgh")  # 17 chars -> 4 tokens
    write_project(vault, "river-ledger", core=["interaction/one", "interaction/two"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["size"]["stanza_count"] == 2
    assert result["size"]["bytes"] == sum(item["bytes"] for item in result["core"])
    assert result["size"]["estimated_tokens"] == 7
    assert result["size"]["estimated_tokens"] == sum(
        item["estimated_tokens"] for item in result["core"]
    )


def test_resolving_global_does_not_double_include(vault: Path) -> None:
    write_stanza(vault, "interaction/summary-first", "GLOBAL-CORE-BODY")
    write_project(vault, "_global", core=["interaction/summary-first"])
    result = resolve_protocol(vault, "_global")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == ["interaction/summary-first"]


def test_prov_files_are_not_stanzas_for_resolution(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    sibling = vault / "stanzas" / "interaction" / "how-i-work-with-ai.prov.md"
    sibling.write_text("# why\nnot a stanza\n", encoding="utf-8")
    why = vault / "provenance" / "interaction" / "how-i-work-with-ai.md"
    why.parent.mkdir(parents=True, exist_ok=True)
    why.write_text("# why\nalso not a stanza\n", encoding="utf-8")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert [item["id"] for item in result["core"]] == ["interaction/how-i-work-with-ai"]
    assert "not a stanza" not in result["core"][0]["content"]
    assert "also not a stanza" not in result["core"][0]["content"]


def test_body_without_a_heading_is_headed_from_the_title(vault: Path) -> None:
    write_stanza(vault, "interaction/one", "PLAIN-BODY", title="Plain body")
    write_project(vault, "river-ledger", core=["interaction/one"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["core"][0]["content"] == "# Plain body\n\nPLAIN-BODY"


def test_body_that_already_has_a_heading_is_not_doubled(vault: Path) -> None:
    write_stanza(vault, "interaction/one", "# Plain body\n\nPLAIN-BODY", title="Plain body")
    write_project(vault, "river-ledger", core=["interaction/one"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["core"][0]["content"] == "# Plain body\n\nPLAIN-BODY"


def test_the_title_wins_when_the_body_heading_disagrees(vault: Path) -> None:
    write_stanza(vault, "interaction/one", "# Stale name\n\nBODY", title="Current name")
    write_project(vault, "river-ledger", core=["interaction/one"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    assert result["core"][0]["content"] == "# Current name\n\nBODY"


def test_every_composed_stanza_opens_its_own_heading(vault: Path) -> None:
    # The failure this replaces: an unheaded body read as more prose under the
    # stanza before it, and the composed file looked plausible either way.
    write_stanza(vault, "interaction/one", "FIRST-BODY", title="First")
    write_stanza(vault, "interaction/two", "SECOND-BODY", title="Second")
    write_project(vault, "river-ledger", core=["interaction/one", "interaction/two"])
    result = resolve_protocol(vault, "river-ledger")
    assert result["ok"] is True
    bodies = [item["content"] for item in result["core"]]
    assert [body.splitlines()[0] for body in bodies] == ["# First", "# Second"]
    assert "\n\n".join(bodies).count("\n# ") == 1
