from __future__ import annotations

from pathlib import Path

import yaml

from helpers import write_article, write_project, write_role, write_skill

from insitu.catalog import get_role, list_roles, list_skills, where_used_skill
from insitu.materialize import materialize
from insitu.mutate import create_role, delete_skill, link_skill, update_role
from insitu.resolve import resolve_protocol
from insitu.store import load_vault
from insitu.validate import validate


def _close_books(vault: Path) -> None:
    write_skill(vault, "close-books", "Run /close-books at end of day.")


def _clerk_role(vault: Path, *, skills: list[str] | None = None) -> None:
    write_article(vault, "methodology/ledger-clerk", "CLERK")
    write_role(
        vault,
        "clerk",
        name="Clerk",
        core=["methodology/ledger-clerk"],
        skills=skills,
    )


def test_role_skills_compose_for_every_subscriber(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    write_project(vault, "harbor-notes", roles=["clerk"])
    for key in ("river-ledger", "harbor-notes"):
        resolved = resolve_protocol(vault, key)
        assert resolved["ok"] is True
        assert [row["id"] for row in resolved["skills"]] == ["close-books"]


def test_role_and_map_same_skill_first_wins(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"], skills=["close-books"])
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is True
    assert [row["id"] for row in resolved["skills"]] == ["close-books"]


def test_missing_skill_on_role_fails_resolve(vault: Path) -> None:
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is False
    assert resolved["error"] == "missing_skill"
    assert resolved["id"] == "close-books"


def test_global_role_skills_do_not_fan_out(vault: Path) -> None:
    _close_books(vault)
    write_article(vault, "interaction/voice", "VOICE")
    write_role(vault, "voice", core=["interaction/voice"], skills=["close-books"])
    write_project(vault, "_global", roles=["voice"])
    write_article(vault, "interaction/how-i-work-with-ai", "PROJECT")
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])
    other = resolve_protocol(vault, "river-ledger")
    assert other["ok"] is True
    assert other["skills"] == []
    own = resolve_protocol(vault, "_global")
    assert [row["id"] for row in own["skills"]] == ["close-books"]


def test_validate_accepts_role_skills(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    report = validate(vault)
    kinds = [item["kind"] for item in report["issues"]]
    assert "role_skills_not_supported" not in kinds
    assert report["ok"] is True
    assert report["findings"]["unreferenced_skill"] == []
    empty = [row["id"] for row in report["findings"]["empty_roles"]]
    assert "clerk" not in empty


def test_create_and_update_role_skills(vault: Path) -> None:
    _close_books(vault)
    write_article(vault, "methodology/ledger-clerk", "CLERK")
    write_skill(vault, "seal-day", "Seal the day.")
    created = create_role(
        vault,
        "clerk",
        core=["methodology/ledger-clerk"],
        skills=["close-books"],
    )
    assert created["ok"] is True
    assert created["skills"] == ["close-books"]
    raw = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert raw["skills"] == ["close-books"]

    write_project(vault, "river-ledger", roles=["clerk"])
    preview = update_role(vault, "clerk", add_skills=["seal-day"])
    assert preview["ok"] is True
    assert preview["written"] is False
    assert "seal-day" in preview["expected"]["add_skills"]
    assert "river-ledger" in preview["expected"]["projects"]

    confirmed = update_role(
        vault,
        "clerk",
        add_skills=["seal-day"],
        confirm=True,
        expected=preview["expected"],
    )
    assert confirmed["ok"] is True
    assert confirmed["written"] is True
    resolved = resolve_protocol(vault, "river-ledger")
    assert [row["id"] for row in resolved["skills"]] == ["close-books", "seal-day"]

    drop = update_role(vault, "clerk", remove_skills=["close-books"])
    dropped = update_role(
        vault,
        "clerk",
        remove_skills=["close-books"],
        confirm=True,
        expected=drop["expected"],
    )
    assert dropped["ok"] is True
    after = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert after["skills"] == ["seal-day"]


def test_where_used_skill_names_roles(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    used = where_used_skill(vault, "close-books")
    assert used["ok"] is True
    assert {"project": "river-ledger", "lists": ["role:clerk"]} in used["used_by"]
    assert {"role": "clerk", "lists": ["skills"]} in used["used_by"]
    listed = list_skills(vault)
    assert listed["skills"][0]["projects"] == ["river-ledger"]
    role = get_role(vault, "clerk")
    assert [row["id"] for row in role["skills"]] == ["close-books"]
    roles = list_roles(vault)
    assert roles["roles"][0]["skills_count"] == 1


def test_delete_skill_unlinks_role(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    preview = delete_skill(vault, "close-books")
    assert "clerk" in preview["expected"]["roles"]
    confirmed = delete_skill(
        vault, "close-books", confirm=True, expected=preview["expected"]
    )
    assert confirmed["ok"] is True
    role = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert "skills" not in role or role.get("skills") == []
    assert not (vault / "skills" / "close-books").exists()


def test_link_skill_already_composed_via_role(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    result = link_skill(vault, "river-ledger", "close-books")
    assert result["ok"] is False
    assert result["error"] == "already_linked"


def test_materialize_writes_role_carried_skill(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    write_project(vault, "river-ledger", roles=["clerk"])
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
    work = vault.parent / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    skill_md = work / ".grok" / "skills" / "close-books" / "SKILL.md"
    assert skill_md.is_file()
    stamp = skill_md.read_text(encoding="utf-8")
    assert "insitu-generated:" in stamp
    assert "skill: close-books" in stamp


def test_loaded_role_exposes_skills(vault: Path) -> None:
    _close_books(vault)
    _clerk_role(vault, skills=["close-books"])
    loaded = load_vault(vault)
    assert loaded.roles["clerk"].skills == ["close-books"]
