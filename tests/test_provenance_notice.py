"""A why-log entry written into the body is warned about where it is written."""

from __future__ import annotations

from pathlib import Path

from insitu.mutate import (
    create_article,
    create_skill,
    update_article,
    update_skill,
)
from insitu.provisions import provenance_in_body

BODY_WITH = "A rule.\n\nReason: it keeps the record honest.\n\nProvenance: 2026-09-04, after a miss."
BODY_WITHOUT = "A rule.\n\nReason: it keeps the record honest."


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def test_a_trailing_provenance_block_is_found(tmp_path: Path) -> None:
    notice = provenance_in_body(BODY_WITH)
    assert notice is not None
    assert notice["code"] == "provenance_in_body"
    assert notice["lines"] == [5]


def test_a_provenance_heading_is_found(tmp_path: Path) -> None:
    notice = provenance_in_body("# Title\n\nBody.\n\n## Provenance\n\n2026-09-04, a thing.")
    assert notice is not None
    assert notice["lines"] == [5]


def test_every_block_is_reported_not_only_the_first(tmp_path: Path) -> None:
    notice = provenance_in_body("Provenance: one.\n\nA rule.\n\nProvenance: two.")
    assert notice is not None
    assert notice["lines"] == [1, 5]


def test_the_word_mid_paragraph_does_not_trip_it(tmp_path: Path) -> None:
    # An article whose subject is provenance has to be writable. The scan is
    # anchored at a block opening precisely so this stays quiet.
    assert provenance_in_body("A why-log lives at provenance/<id>.md and is not an article.") is None
    assert provenance_in_body("A rule.\n\nThe provenance of this rule is unclear.") is None
    assert provenance_in_body(BODY_WITHOUT) is None


def test_create_article_warns_and_still_writes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    result = create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITH,
        why="seeded",
    )
    assert result["ok"] is True
    # A warning, never a refusal: the article is on disk and the why-log with it.
    assert (vault / "articles" / "methodology" / "thing.md").is_file()
    assert result["provenance_in_body"]["code"] == "provenance_in_body"
    # The detail points at a key the same result carries.
    assert result["why_log"] == "provenance/methodology/thing.md"


def test_create_article_stays_quiet_on_a_clean_body(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    result = create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITHOUT,
        why="seeded",
    )
    assert result["ok"] is True
    assert "provenance_in_body" not in result


def test_update_article_scans_the_body_it_wrote(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITHOUT,
        why="seeded",
    )
    added = update_article(vault, "methodology/thing", why="add it", content=BODY_WITH)
    assert added["provenance_in_body"]["lines"] == [5]
    removed = update_article(vault, "methodology/thing", why="take it out", content=BODY_WITHOUT)
    assert "provenance_in_body" not in removed


def test_a_title_only_update_still_reports_a_body_that_has_one(tmp_path: Path) -> None:
    # The condition is the state of the body, not of this edit. It persists until
    # someone fixes it, which is the point: an article that carries provenance
    # keeps saying so every time anyone opens it to change something else.
    vault = _vault(tmp_path)
    create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITH,
        why="seeded",
    )
    renamed = update_article(vault, "methodology/thing", why="rename", title="Thing renamed")
    assert renamed["ok"] is True
    assert renamed["provenance_in_body"]["code"] == "provenance_in_body"


def test_skills_get_the_same_notice(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    created = create_skill(
        vault,
        "doer",
        description="Does a thing.",
        content=BODY_WITH,
        why="seeded",
    )
    assert created["ok"] is True
    assert created["provenance_in_body"]["code"] == "provenance_in_body"
    assert created["why_log"] == "provenance/skills/doer.md"

    cleaned = update_skill(vault, "doer", why="take it out", content=BODY_WITHOUT)
    assert "provenance_in_body" not in cleaned


def test_update_skill_returns_its_why_log_so_the_notice_resolves(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    create_skill(vault, "doer", description="Does a thing.", content=BODY_WITHOUT, why="seeded")
    result = update_skill(vault, "doer", why="add it", content=BODY_WITH)
    assert result["why_log"] == "provenance/skills/doer.md"
    assert result["provenance_in_body"]["code"] == "provenance_in_body"


def test_a_refusal_carries_no_notice(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITH,
        why="seeded",
    )
    again = create_article(
        vault,
        "methodology/thing",
        title="Thing",
        description="A thing.",
        content=BODY_WITH,
        why="seeded",
    )
    assert again["ok"] is False
    assert again["error"] == "article_exists"
    assert "provenance_in_body" not in again
