"""The on-demand index reaches the file a host loads, not only the tool result."""

from __future__ import annotations

from pathlib import Path

import yaml
from helpers import write_article, write_project

from insitu.materialize import materialize, render_on_demand

SURFACES = {"surfaces": ["grok", "claude", "cursor"]}


def _seed(vault: Path) -> None:
    write_article(vault, "interaction/summary-first", "CORE-BODY")
    write_article(
        vault,
        "methodology/river-survey",
        "ON-DEMAND-BODY",
        title="River survey",
        description="How this chair surveys a river before it maps one.",
    )
    write_project(
        vault,
        "river-ledger",
        core=["interaction/summary-first"],
        on_demand=["methodology/river-survey"],
    )


def _work(tmp_path: Path, vault: Path) -> Path:
    (vault / "config").mkdir(parents=True, exist_ok=True)
    (vault / "config" / "surfaces.yaml").write_text(yaml.safe_dump(SURFACES), encoding="utf-8")
    work = tmp_path / "river-ledger"
    work.mkdir()
    return work


def test_the_index_names_the_article_its_cost_and_when_to_pull(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = _work(tmp_path, vault)
    assert materialize(vault, work, project="river-ledger")["ok"] is True

    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "# On demand" in protocol
    assert "`methodology/river-survey`" in protocol
    # The description is the trigger surface: without it the id says nothing
    # about when the work calls for the article.
    assert "How this chair surveys a river before it maps one." in protocol
    assert "tokens)" in protocol
    assert "get_article" in protocol
    # An index, never the body.
    assert "ON-DEMAND-BODY" not in protocol


def test_every_surface_carries_it_since_the_adapter_is_what_loads(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = _work(tmp_path, vault)
    materialize(vault, work, project="river-ledger")
    for rel in (
        ".grok/rules/insitu-protocol.md",
        ".claude/rules/insitu-protocol.md",
        ".cursor/rules/insitu-protocol.mdc",
    ):
        text = (work / rel).read_text(encoding="utf-8")
        assert "# On demand" in text, rel
        assert "`methodology/river-survey`" in text, rel


def test_the_index_sits_between_the_header_and_the_doctrine(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = _work(tmp_path, vault)
    materialize(vault, work, project="river-ledger")
    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert protocol.index("-->") < protocol.index("# On demand") < protocol.index("CORE-BODY")


def test_a_chair_with_nothing_on_demand_gets_no_heading(vault: Path, tmp_path: Path) -> None:
    write_article(vault, "interaction/summary-first", "CORE-BODY")
    write_project(vault, "river-ledger", core=["interaction/summary-first"])
    work = _work(tmp_path, vault)
    materialize(vault, work, project="river-ledger")
    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "On demand" not in protocol
    # An empty section would be weight for nothing, and the header still ends
    # where the doctrine begins.
    assert protocol.index("-->") < protocol.index("CORE-BODY")


def test_a_chair_with_no_core_still_gets_its_index(vault: Path, tmp_path: Path) -> None:
    # The two lists are independent. A chair may carry nothing and still be able
    # to reach for something.
    write_article(vault, "methodology/river-survey", "ON-DEMAND-BODY")
    write_project(vault, "river-ledger", on_demand=["methodology/river-survey"])
    work = _work(tmp_path, vault)
    materialize(vault, work, project="river-ledger")
    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "# On demand" in protocol
    assert protocol.endswith("\n")


def test_render_is_empty_for_an_empty_set(vault: Path) -> None:
    assert render_on_demand([]) == ""


def test_render_survives_a_missing_size_or_description(vault: Path) -> None:
    out = render_on_demand([{"id": "methodology/bare"}])
    assert out.strip().endswith("- `methodology/bare`")
