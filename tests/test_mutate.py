from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from helpers import write_project, write_stanza

from insitu.catalog import get_stanza, where_used
from insitu.mutate import create_stanza, link_stanza, unlink_stanza, update_stanza
from insitu.validate import validate


GIT = shutil.which("git")


def _git(vault: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=vault,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git(vault: Path) -> None:
    _git(vault, "init")
    _git(vault, "config", "user.email", "test@example.com")
    _git(vault, "config", "user.name", "Test")
    _git(vault, "add", ".")
    _git(vault, "commit", "-m", "seed", "--allow-empty")


def test_create_stanza_writes_file_and_why_log(vault: Path) -> None:
    result = create_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        title="How I work with AI",
        description="Standing prefs",
        content="Say the decision in one sentence.\n",
        why="First capture of the standing prefs.",
        tags=["interaction"],
    )
    assert result["ok"] is True
    assert result["id"] == "interaction/how-i-work-with-ai"
    assert result["title"] == "How I work with AI"
    assert "Say the decision" in result["content"]
    assert result["review"] == "review"
    assert result["committed"] is False
    assert result["why_log"] == "provenance/interaction/how-i-work-with-ai.md"

    path = vault / "stanzas" / "interaction" / "how-i-work-with-ai.md"
    text = path.read_text(encoding="utf-8")
    assert "title: How I work with AI" in text
    assert "id: interaction/how-i-work-with-ai" in text

    prov = vault / "provenance" / "interaction" / "how-i-work-with-ai.md"
    log = prov.read_text(encoding="utf-8")
    assert log.startswith("# Provenance — interaction/how-i-work-with-ai\n")
    assert f"## {date.today().isoformat()}\n" in log
    assert "Why: First capture of the standing prefs." in log

    loaded = get_stanza(vault, "interaction/how-i-work-with-ai")
    assert loaded["ok"] is True
    assert loaded["tags"] == ["interaction"]


def test_create_stanza_rejects_existing_and_missing_why(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "OLD")
    exists = create_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        title="T",
        description="D",
        content="NEW",
        why="try overwrite",
    )
    assert exists == {
        "ok": False,
        "error": "stanza_exists",
        "id": "interaction/how-i-work-with-ai",
    }
    assert (
        vault / "stanzas" / "interaction" / "how-i-work-with-ai.md"
    ).read_text(encoding="utf-8").count("OLD") == 1

    missing_why = create_stanza(
        vault,
        "methodology/small-diffs",
        title="Small diffs",
        description="Keep changes small",
        content="Keep it small.",
        why="   ",
    )
    assert missing_why["ok"] is False
    assert missing_why["error"] == "missing_why"


def test_update_stanza_appends_why_log_and_returns_where_used(vault: Path) -> None:
    write_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        "OLD-BODY",
        title="How I work with AI",
        description="Standing prefs",
    )
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    prov = vault / "provenance" / "interaction" / "how-i-work-with-ai.md"
    prov.parent.mkdir(parents=True, exist_ok=True)
    prov.write_text(
        "# Provenance — interaction/how-i-work-with-ai\n\n## 2026-08-16\nWhy: Seeded.\n",
        encoding="utf-8",
    )

    result = update_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        content="NEW-BODY\n",
        why="Tighten the body.",
    )
    assert result["ok"] is True
    assert "NEW-BODY" in result["content"]
    assert result["where_used"] == where_used(vault, "interaction/how-i-work-with-ai")
    assert result["where_used"]["used_by"] == [
        {"project": "river-ledger", "lists": ["core"]}
    ]
    assert result["why_log"] == "provenance/interaction/how-i-work-with-ai.md"

    log = prov.read_text(encoding="utf-8")
    assert "Why: Seeded." in log
    assert "Why: Tighten the body." in log
    assert log.count("# Provenance") == 1


def test_update_stanza_requires_a_change(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    missing = update_stanza(vault, "interaction/missing-piece", why="n/a")
    assert missing == {"ok": False, "error": "missing_stanza", "id": "interaction/missing-piece"}

    no_fields = update_stanza(vault, "interaction/how-i-work-with-ai", why="n/a")
    assert no_fields["error"] == "no_changes"


def test_link_and_unlink_are_map_only(vault: Path) -> None:
    write_stanza(vault, "methodology/small-diffs", "KEEP IT SMALL")
    write_project(vault, "river-ledger", core=["interaction/local"])
    write_stanza(vault, "interaction/local", "LOCAL")

    linked = link_stanza(
        vault, "river-ledger", "methodology/small-diffs", target="on_demand"
    )
    assert linked["ok"] is True
    assert linked["target"] == "on_demand"
    assert linked["on_demand"] == ["methodology/small-diffs"]
    assert linked["core"] == ["interaction/local"]
    data = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["on_demand"] == ["methodology/small-diffs"]
    assert not (vault / "provenance" / "methodology" / "small-diffs.md").exists()
    assert not (vault / "stanzas" / "methodology" / "small-diffs.prov.md").exists()

    again = link_stanza(
        vault, "river-ledger", "methodology/small-diffs", target="on_demand"
    )
    assert again["error"] == "already_linked"
    assert again["target"] == "on_demand"

    other_list = link_stanza(
        vault, "river-ledger", "methodology/small-diffs", target="core"
    )
    assert other_list["error"] == "already_linked"

    removed = unlink_stanza(vault, "river-ledger", "methodology/small-diffs")
    assert removed["ok"] is True
    after = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert after["on_demand"] == []
    assert after["core"] == ["interaction/local"]

    missing = unlink_stanza(vault, "river-ledger", "methodology/small-diffs")
    assert missing["error"] == "not_linked"


def test_link_rejects_missing_project_and_stanza(vault: Path) -> None:
    write_stanza(vault, "methodology/small-diffs", "BODY")
    write_project(vault, "river-ledger")
    assert link_stanza(vault, "ghost", "methodology/small-diffs")["error"] == "missing_project"
    assert link_stanza(vault, "river-ledger", "methodology/ghost")["error"] == "missing_stanza"


@pytest.mark.skipif(GIT is None, reason="git not available")
def test_review_policy_stages_and_auto_commits(vault: Path) -> None:
    _init_git(vault)
    create_stanza(
        vault,
        "interaction/summary-first",
        title="Summary first",
        description="Form",
        content="Thesis first.",
        why="Add the form.",
    )
    staged = _git(vault, "diff", "--cached", "--name-only")
    names = {line.replace("\\", "/") for line in staged.stdout.splitlines() if line}
    assert "stanzas/interaction/summary-first.md" in names
    assert "provenance/interaction/summary-first.md" in names
    head = _git(vault, "log", "-1", "--pretty=%s")
    assert "seed" in head.stdout

    policy = vault / "config" / "review-policy.yaml"
    policy.write_text("default: auto\n", encoding="utf-8")
    created = create_stanza(
        vault,
        "methodology/small-diffs",
        title="Small diffs",
        description="Keep changes small",
        content="Small.",
        why="Add the method.",
    )
    assert created["review"] == "auto"
    assert created["committed"] is True
    head = _git(vault, "log", "-1", "--pretty=%s")
    assert "create stanza methodology/small-diffs" in head.stdout


def test_update_migrates_leftover_sibling_why_log(vault: Path) -> None:
    write_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        "OLD-BODY",
        title="How I work with AI",
        description="Standing prefs",
    )
    sibling = vault / "stanzas" / "interaction" / "how-i-work-with-ai.prov.md"
    sibling.write_text(
        "# Provenance — interaction/how-i-work-with-ai\n\n## 2026-08-16\nWhy: Seeded.\n",
        encoding="utf-8",
    )

    result = update_stanza(
        vault,
        "interaction/how-i-work-with-ai",
        content="NEW-BODY\n",
        why="Move the why-log.",
    )
    assert result["ok"] is True
    dest = vault / "provenance" / "interaction" / "how-i-work-with-ai.md"
    assert dest.is_file()
    assert not sibling.exists()
    log = dest.read_text(encoding="utf-8")
    assert "Why: Seeded." in log
    assert "Why: Move the why-log." in log


@pytest.mark.skipif(GIT is None, reason="git not available")
def test_validate_fix_follows_review_dial(vault: Path) -> None:
    write_stanza(vault, "interaction/shared", "S")
    write_stanza(vault, "interaction/local", "L")
    write_project(vault, "_global", core=["interaction/shared"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/shared", "interaction/local", "interaction/local"],
    )
    _init_git(vault)
    (vault / "config" / "review-policy.yaml").write_text("default: auto\n", encoding="utf-8")
    _git(vault, "add", "config/review-policy.yaml")
    _git(vault, "commit", "-m", "policy")

    report = validate(vault, fix=True)
    assert any(item.get("kind") == "duplicate" for item in report.get("fixed", []))
    assert report["review"] == "auto"
    assert report["committed"] is True
    head = _git(vault, "log", "-1", "--pretty=%s")
    assert "validate" in head.stdout
