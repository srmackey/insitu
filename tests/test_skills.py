from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml

from helpers import write_project, write_role, write_skill, write_stanza

from insitu.catalog import get_project, get_skill, list_skills, where_used_skill
from insitu.materialize import materialize
from insitu.mutate import (
    create_project,
    create_skill,
    delete_skill,
    link_skill,
    link_stanza,
    unlink_skill,
    update_project,
    update_skill,
)
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _close_books(vault: Path) -> None:
    write_skill(
        vault,
        "close-books",
        "Run /close-books at end of day.",
        payload={"scripts/close.py": "print('closed')\n"},
        extra_files={"notes.md": "scratch, not copied\n"},
    )


def _seed_project(vault: Path, *, skills: list[str] | None = None) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"], skills=skills)


def test_list_and_get_skill_see_payload_not_notes(vault: Path) -> None:
    _close_books(vault)
    write_project(vault, "river-ledger", skills=["close-books"])
    listed = list_skills(vault)
    assert listed["ok"] is True
    rows = listed["skills"]
    assert len(rows) == 1
    assert rows[0]["id"] == "close-books"
    assert rows[0]["name"] == "close-books"
    assert "description" in rows[0]
    assert "bytes" in rows[0]
    assert "river-ledger" in rows[0]["projects"]
    got = get_skill(vault, "close-books")
    assert got["ok"] is True
    assert got["content"] == "Run /close-books at end of day."
    assert "scripts/close.py" in got["payload"]
    assert "notes.md" not in got["payload"]
    assert "notes.md" not in got["content"]


def test_link_skill_writes_and_unlink_omits_empty_key(vault: Path) -> None:
    _close_books(vault)
    _seed_project(vault)
    linked = link_skill(vault, "river-ledger", "close-books")
    assert linked["ok"] is True
    assert linked["skills"] == ["close-books"]
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert raw["skills"] == ["close-books"]
    again = link_skill(vault, "river-ledger", "close-books")
    assert again["ok"] is False
    assert again["error"] == "already_linked"
    unlinked = unlink_skill(vault, "river-ledger", "close-books")
    assert unlinked["ok"] is True
    assert unlinked["skills"] == []
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert "skills" not in raw
    missing = unlink_skill(vault, "river-ledger", "close-books")
    assert missing["ok"] is False
    assert missing["error"] == "not_linked"


def test_link_stanza_target_skills_is_invalid(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    result = link_stanza(vault, "river-ledger", "interaction/how-i-work-with-ai", target="skills")
    assert result["ok"] is False
    assert result["error"] == "invalid_target"


def test_missing_skill_id_is_hard_error(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai"],
        skills=["close-books"],
    )
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is False
    assert resolved["error"] == "missing_skill"
    assert resolved["id"] == "close-books"
    work = vault.parent / "river-ledger"
    work.mkdir()
    written = materialize(vault, work, project="river-ledger")
    assert written["ok"] is False
    assert written["error"] == "missing_skill"


def test_resolve_protocol_skills_index_not_in_core(vault: Path) -> None:
    _close_books(vault)
    _seed_project(vault, skills=["close-books"])
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is True
    assert [item["id"] for item in resolved["core"]] == ["interaction/how-i-work-with-ai"]
    assert "Run /close-books" not in "".join(item["content"] for item in resolved["core"])
    skills = resolved["skills"]
    assert len(skills) == 1
    assert skills[0]["id"] == "close-books"
    assert skills[0]["name"] == "close-books"
    assert "content" not in skills[0]
    assert skills[0]["bytes"] > 0
    summary = get_project(vault, "river-ledger")
    assert summary["ok"] is True
    assert summary["skills"] == ["close-books"]
    assert summary["skills_size"]["count"] == 1
    assert summary["skills_size"]["bytes"] > 0


def test_role_skills_not_supported(vault: Path) -> None:
    write_stanza(vault, "methodology/ledger-clerk", "BODY")
    write_role(vault, "clerk", core=["methodology/ledger-clerk"], extra={"skills": ["close-books"]})
    write_project(vault, "river-ledger", roles=["clerk"])
    report = validate(vault)
    kinds = [item["kind"] for item in report["issues"]]
    assert "role_skills_not_supported" in kinds
    assert report["ok"] is False
    fixed = validate(vault, fix=True)
    kinds = [item["kind"] for item in fixed["issues"]]
    assert "role_skills_not_supported" in kinds


def test_global_skills_not_inherited(vault: Path) -> None:
    _close_books(vault)
    write_skill(vault, "other-skill", "Other procedure.")
    write_stanza(vault, "interaction/digest-then-drill", "GLOBAL")
    write_stanza(vault, "interaction/how-i-work-with-ai", "PROJECT")
    write_project(vault, "_global", core=["interaction/digest-then-drill"], skills=["close-books"])
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is True
    assert resolved["skills"] == []
    report = validate(vault)
    assert report["ok"] is True
    assert report["findings"]["global_skills_not_inherited"]
    assert any(item.get("project") == "_global" for item in report["findings"]["global_skills_not_inherited"])
    global_resolved = resolve_protocol(vault, "_global")
    assert [row["id"] for row in global_resolved["skills"]] == ["close-books"]


def test_materialize_writes_skill_trees_stamp_after_frontmatter(
    vault: Path, tmp_path: Path
) -> None:
    _close_books(vault)
    _seed_project(vault, skills=["close-books"])
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "claude"]}),
        encoding="utf-8",
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    written_ids = [row["id"] for row in result["skills"]]
    assert written_ids == ["close-books"]
    grok = work / ".grok" / "skills" / "close-books" / "SKILL.md"
    claude = work / ".claude" / "skills" / "close-books" / "SKILL.md"
    assert grok.is_file()
    assert claude.is_file()
    text = grok.read_text(encoding="utf-8")
    post = frontmatter.loads(text)
    assert post.metadata["name"] == "close-books"
    assert post.metadata["description"]
    body = post.content.lstrip()
    assert body.startswith("<!--")
    assert "insitu-generated: true" in body
    assert "skill: close-books" in body
    assert "Run /close-books at end of day." in body
    assert (work / ".grok" / "skills" / "close-books" / "scripts" / "close.py").is_file()
    assert not (work / ".grok" / "skills" / "close-books" / "notes.md").exists()
    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "Run /close-books at end of day." not in protocol


def test_materialize_orphan_cleanup_leaves_unstamped(
    vault: Path, tmp_path: Path
) -> None:
    _close_books(vault)
    _seed_project(vault, skills=["close-books"])
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    first = materialize(vault, work, project="river-ledger")
    assert first["ok"] is True
    local = work / ".grok" / "skills" / "local-only"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text(
        "---\nname: local-only\ndescription: hand authored\n---\n\nStay.\n",
        encoding="utf-8",
    )
    unlink_skill(vault, "river-ledger", "close-books")
    second = materialize(vault, work, project="river-ledger")
    assert second["ok"] is True
    removed = {(row["surface"], row["id"]) for row in second["skills_removed"]}
    assert ("grok", "close-books") in removed
    assert not (work / ".grok" / "skills" / "close-books").exists()
    assert (local / "SKILL.md").is_file()
    assert "Stay." in (local / "SKILL.md").read_text(encoding="utf-8")


def test_materialize_skills_need_surfaces_warning(vault: Path, tmp_path: Path) -> None:
    _close_books(vault)
    _seed_project(vault, skills=["close-books"])
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert "no_surfaces_configured" in result["warnings"]
    assert "skills_need_surfaces" in result["warnings"]
    assert (work / "PROTOCOL.md").is_file()
    assert not (work / ".grok").exists()
    assert result["skills"] == []


def test_delete_skill_preview_and_confirm(vault: Path) -> None:
    _close_books(vault)
    write_skill(vault, "other-skill", "Keep this one.")
    _seed_project(vault, skills=["close-books"])
    (vault / "provenance" / "skills").mkdir(parents=True)
    (vault / "provenance" / "skills" / "close-books.md").write_text(
        "# Provenance — close-books\n",
        encoding="utf-8",
    )
    preview = delete_skill(vault, "close-books")
    assert preview["ok"] is True
    assert preview["written"] is False
    assert (vault / "skills" / "close-books" / "SKILL.md").is_file()
    confirmed = delete_skill(
        vault,
        "close-books",
        confirm=True,
        expected=preview["expected"],
    )
    assert confirmed["ok"] is True
    assert confirmed["written"] is True
    assert not (vault / "skills" / "close-books").exists()
    assert not (vault / "provenance" / "skills" / "close-books.md").exists()
    assert (vault / "skills" / "other-skill" / "SKILL.md").is_file()
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert "skills" not in raw


def test_where_used_skill_lists_maps_only(vault: Path) -> None:
    _close_books(vault)
    write_stanza(vault, "methodology/ledger-clerk", "BODY")
    write_role(vault, "clerk", core=["methodology/ledger-clerk"], extra={"skills": ["close-books"]})
    write_project(vault, "river-ledger", roles=["clerk"], skills=["close-books"])
    used = where_used_skill(vault, "close-books")
    assert used["ok"] is True
    assert used["used_by"] == [{"project": "river-ledger", "lists": ["skills"]}]
    assert all("role" not in row for row in used["used_by"])


def test_update_skill_affects_projects(vault: Path) -> None:
    _close_books(vault)
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"], skills=["close-books"])
    write_project(vault, "harbor-notes", skills=["close-books"])
    result = update_skill(
        vault,
        "close-books",
        description="Close the ledger and archive the day.",
        content="Updated procedure.",
    )
    assert result["ok"] is True
    assert result["affects_projects"] == ["harbor-notes", "river-ledger"]
    got = get_skill(vault, "close-books")
    assert got["description"] == "Close the ledger and archive the day."
    assert got["content"] == "Updated procedure."


def test_create_skill_does_not_auto_link(vault: Path) -> None:
    _seed_project(vault)
    created = create_skill(
        vault,
        "close-books",
        description="Close the day's books.",
        content="Run it.",
        why="first catalog row",
    )
    assert created["ok"] is True
    assert created["affects_projects"] == []
    assert (vault / "skills" / "close-books" / "SKILL.md").is_file()
    assert (vault / "provenance" / "skills" / "close-books.md").is_file()
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert "skills" not in (raw or {})


def test_create_project_skills_missing_is_error(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    result = create_project(
        vault,
        "harbor-notes",
        core=["interaction/how-i-work-with-ai"],
        skills=["close-books"],
    )
    assert result["ok"] is False
    assert result["error"] == "missing_skill"


def test_update_project_add_remove_skills(vault: Path) -> None:
    _close_books(vault)
    _seed_project(vault)
    added = update_project(vault, "river-ledger", add_skills=["close-books"])
    assert added["ok"] is True
    assert added["skills"] == ["close-books"]
    removed = update_project(vault, "river-ledger", remove_skills=["close-books"])
    assert removed["ok"] is True
    assert removed["skills"] == []
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert "skills" not in raw


def test_validate_skill_findings_and_duplicate_fix(vault: Path) -> None:
    _close_books(vault)
    write_skill(vault, "other-skill", "Unreferenced procedure.")
    (vault / "skills" / "empty-dir").mkdir(parents=True)
    nested = vault / "skills" / "methodology" / "land"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(
        "---\nname: land\ndescription: nested\n---\n\nNo.\n",
        encoding="utf-8",
    )
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai"],
        skills=["close-books", "close-books"],
    )
    report = validate(vault)
    issue_kinds = {item["kind"] for item in report["issues"]}
    assert "duplicate" in issue_kinds
    assert "invalid_skill_path" in issue_kinds
    finding_ids = {item["id"] for item in report["findings"]["unreferenced_skill"]}
    assert "other-skill" in finding_ids
    assert "close-books" not in finding_ids
    missing_md = {item["id"] for item in report["findings"]["skill_missing_skill_md"]}
    assert "empty-dir" in missing_md
    empty = [item for item in report["findings"]["empty_projects"] if item["id"] == "river-ledger"]
    assert empty == []
    fixed = validate(vault, fix=True)
    raw = yaml.safe_load((vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8"))
    assert raw["skills"] == ["close-books"]
    leftover = [item for item in fixed["issues"] if item["kind"] == "duplicate" and item.get("list") == "skills"]
    assert leftover == []
    assert (vault / "skills" / "other-skill" / "SKILL.md").is_file()


def test_empty_skills_do_not_fill_a_project(vault: Path) -> None:
    write_project(vault, "harbor-notes")
    report = validate(vault)
    ids = [item["id"] for item in report["findings"]["empty_projects"]]
    assert "harbor-notes" in ids


def test_load_omits_missing_skills_key(vault: Path) -> None:
    write_stanza(vault, "interaction/how-i-work-with-ai", "BODY")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    loaded = load_vault(vault)
    assert loaded.projects["river-ledger"].skills == []
