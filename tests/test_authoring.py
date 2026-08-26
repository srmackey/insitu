from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from helpers import write_project, write_role, write_stanza

from insitu.mutate import (
    create_project,
    create_role,
    create_stanza,
    delete_project,
    delete_role,
    delete_stanza,
    link_stanza,
    update_project,
    update_role,
    update_stanza,
)
from insitu.store import load_vault
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


def _seed_linked(vault: Path) -> None:
    write_stanza(
        vault,
        "interaction/voice",
        "VOICE-BODY",
        title="Voice",
        extra_fm={"roles": ["clerk"]},
    )
    write_stanza(
        vault,
        "methodology/clerk-intake",
        "CLERK-CORE",
        title="Clerk intake",
        extra_fm={"roles": ["clerk"]},
    )
    write_stanza(vault, "methodology/orphan", "ORPHAN-BODY", title="Orphan")
    write_role(
        vault,
        "clerk",
        name="Clerk",
        core=["interaction/voice", "methodology/clerk-intake"],
    )
    write_project(vault, "_global", core=["interaction/voice"])
    write_project(
        vault,
        "river-ledger",
        roles=["clerk"],
        core=["methodology/clerk-intake"],
    )


def test_delete_stanza_preview_does_not_write(vault: Path) -> None:
    _seed_linked(vault)
    path = vault / "stanzas" / "methodology" / "clerk-intake.md"
    before = path.read_bytes()

    preview = delete_stanza(vault, "methodology/clerk-intake", why="remove clerk intake")
    assert preview["ok"] is True
    assert preview["written"] is False
    assert preview["id"] == "methodology/clerk-intake"
    assert preview["title"] == "Clerk intake"
    assert "roles" in preview["expected"]
    assert "projects" in preview["expected"]
    assert "clerk" in preview["expected"]["roles"]
    assert "river-ledger" in preview["expected"]["projects"]
    assert path.read_bytes() == before
    role = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert "methodology/clerk-intake" in role["core"]


def test_delete_stanza_confirm_unlinks_then_deletes(vault: Path) -> None:
    _seed_linked(vault)
    path = vault / "stanzas" / "methodology" / "clerk-intake.md"
    prov = vault / "provenance" / "methodology" / "clerk-intake.md"
    leftover = vault / "stanzas" / "methodology" / "clerk-intake.prov.md"
    prov.parent.mkdir(parents=True, exist_ok=True)
    prov.write_text("# Provenance — methodology/clerk-intake\n", encoding="utf-8")
    leftover.write_text("# leftover sibling\n", encoding="utf-8")

    preview = delete_stanza(vault, "methodology/clerk-intake", why="remove clerk intake")
    result = delete_stanza(
        vault,
        "methodology/clerk-intake",
        why="remove clerk intake",
        confirm=True,
        expected=preview["expected"],
    )
    assert result["ok"] is True
    assert result["written"] is True
    assert not path.is_file()
    assert not prov.is_file()
    assert not leftover.is_file()

    role = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert "methodology/clerk-intake" not in role["core"]
    river = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert "methodology/clerk-intake" not in river["core"]
    assert river["roles"] == ["clerk"]
    global_map = yaml.safe_load(
        (vault / "projects" / "_global" / "map.yaml").read_text(encoding="utf-8")
    )
    assert global_map["core"] == ["interaction/voice"]
    assert "river-ledger" in result["affects_projects"]


def test_delete_stanza_confirm_on_gone_id_is_not_found(vault: Path) -> None:
    result = delete_stanza(
        vault,
        "methodology/ghost",
        why="already gone",
        confirm=True,
        expected={"roles": [], "projects": []},
    )
    assert result["ok"] is False
    assert result["error"] == "not_found"
    assert result["id"] == "methodology/ghost"


def test_stale_preview_after_new_link_does_not_delete(vault: Path) -> None:
    write_stanza(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_project(vault, "river-ledger")
    write_project(vault, "harbor-notes")

    preview = delete_stanza(vault, "methodology/small-diffs", why="try delete")
    link_stanza(vault, "harbor-notes", "methodology/small-diffs")
    result = delete_stanza(
        vault,
        "methodology/small-diffs",
        why="try delete",
        confirm=True,
        expected=preview["expected"],
    )
    assert result["error"] == "stale_preview"
    assert result.get("written") is False
    assert (vault / "stanzas" / "methodology" / "small-diffs.md").is_file()
    harbor = yaml.safe_load(
        (vault / "projects" / "harbor-notes" / "map.yaml").read_text(encoding="utf-8")
    )
    assert harbor["core"] == ["methodology/small-diffs"]


def test_cannot_delete_global(vault: Path) -> None:
    write_project(vault, "_global")
    result = delete_project(
        vault, "_global", confirm=True, expected={"projects": ["_global"]}
    )
    assert result["ok"] is False
    assert result["error"] == "cannot_delete_global"
    assert (vault / "projects" / "_global" / "map.yaml").is_file()


def test_create_global_when_missing_and_update_add_remove(vault: Path) -> None:
    write_stanza(vault, "interaction/voice", "VOICE")
    write_stanza(vault, "interaction/extra", "EXTRA")
    created = create_project(vault, "_global", core=["interaction/voice"])
    assert created["ok"] is True
    assert created["affects_projects"] == ["_global"]
    assert (vault / "projects" / "_global" / "map.yaml").is_file()

    again = create_project(vault, "_global")
    assert again["error"] == "already_exists"

    updated = update_project(
        vault,
        "_global",
        add_core=["interaction/extra"],
        remove_core=["interaction/voice"],
    )
    assert updated["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "_global" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["core"] == ["interaction/extra"]


def test_role_add_member_preview_and_confirm(vault: Path) -> None:
    write_stanza(
        vault,
        "methodology/clerk-intake",
        "CLERK",
        title="Clerk intake",
        extra_fm={"roles": ["clerk"]},
    )
    write_stanza(vault, "methodology/clerk-extra", "EXTRA", title="Clerk extra")
    write_role(vault, "clerk", name="Clerk", core=["methodology/clerk-intake"])
    write_project(vault, "river-ledger", roles=["clerk"])
    map_before = (vault / "projects" / "river-ledger" / "map.yaml").read_bytes()

    preview = update_role(vault, "clerk", add_core=["methodology/clerk-extra"])
    assert preview["ok"] is True
    assert preview["written"] is False
    assert "river-ledger" in preview["expected"]["projects"]
    assert "methodology/clerk-extra" in preview["expected"]["add_core"]
    assert (vault / "projects" / "river-ledger" / "map.yaml").read_bytes() == map_before
    role = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert role["core"] == ["methodology/clerk-intake"]

    result = update_role(
        vault,
        "clerk",
        add_core=["methodology/clerk-extra"],
        confirm=True,
        expected=preview["expected"],
    )
    assert result["ok"] is True
    assert result["written"] is True
    assert result["affects_projects"] == ["river-ledger"]
    after_role = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert after_role["core"] == ["methodology/clerk-intake", "methodology/clerk-extra"]
    loaded = load_vault(vault)
    assert "clerk" in loaded.stanzas["methodology/clerk-extra"].roles
    assert (vault / "projects" / "river-ledger" / "map.yaml").read_bytes() == map_before


def test_first_wins_already_in_protocol_via_global(vault: Path) -> None:
    write_stanza(vault, "interaction/voice", "VOICE", title="Voice")
    write_stanza(
        vault,
        "methodology/clerk-intake",
        "CLERK",
        extra_fm={"roles": ["clerk"]},
    )
    write_role(vault, "clerk", core=["methodology/clerk-intake"])
    write_project(vault, "_global", core=["interaction/voice"])
    write_project(vault, "river-ledger", roles=["clerk"])

    preview = update_role(vault, "clerk", add_core=["interaction/voice"])
    river = next(row for row in preview["projects"] if row["project"] == "river-ledger")
    match = next(item for item in river["stanzas"] if item["id"] == "interaction/voice")
    assert match["already_in_protocol"] is True


def test_attach_role_writes_immediately_with_members_and_weight(vault: Path) -> None:
    write_stanza(
        vault,
        "methodology/clerk-intake",
        "CLERK-CORE-BODY",
        title="Clerk intake",
        extra_fm={"roles": ["clerk"]},
    )
    write_role(vault, "clerk", name="Clerk", core=["methodology/clerk-intake"])
    write_project(vault, "harbor-notes")

    result = update_project(vault, "harbor-notes", add_roles=["clerk"])
    assert result["ok"] is True
    assert result.get("written") is True
    assert result["affects_projects"] == ["harbor-notes"]
    member_ids = {item["id"] for item in result["members"]}
    assert "methodology/clerk-intake" in member_ids
    assert result["size"]["stanza_count"] == 1
    data = yaml.safe_load(
        (vault / "projects" / "harbor-notes" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["roles"] == ["clerk"]


def test_validate_findings_empty_unreferenced_and_not_in_protocol(vault: Path) -> None:
    write_stanza(vault, "methodology/orphan", "ORPHAN", title="Orphan")
    write_stanza(
        vault,
        "methodology/idle-role",
        "IDLE",
        title="Idle role stanza",
        extra_fm={"roles": ["idle"]},
    )
    write_stanza(vault, "interaction/global-avail", "GAVAIL", title="Global available")
    write_role(vault, "idle", name="Idle", core=["methodology/idle-role"])
    write_role(vault, "empty-role", name="Empty")
    write_project(vault, "_global", available=["interaction/global-avail"])
    write_project(vault, "empty-harbor")

    report = validate(vault)
    assert report["ok"] is True
    assert report["issues"] == []
    findings = report["findings"]
    empty_projects = {item["id"] for item in findings["empty_projects"]}
    assert "empty-harbor" in empty_projects
    assert "_global" not in empty_projects
    empty_roles = {item["id"] for item in findings["empty_roles"]}
    assert "empty-role" in empty_roles
    unreferenced = {item["id"] for item in findings["unreferenced"]}
    assert "methodology/orphan" in unreferenced
    not_in = {item["id"] for item in findings["not_in_any_protocol"]}
    assert "methodology/idle-role" in not_in
    assert "interaction/global-avail" in not_in
    assert "methodology/orphan" not in not_in


def test_validate_lists_empty_global_as_finding(vault: Path) -> None:
    write_project(vault, "_global")
    report = validate(vault)
    assert report["ok"] is True
    assert any(item["id"] == "_global" for item in report["findings"]["empty_projects"])


def test_validate_issues_fail_ok_findings_do_not(vault: Path) -> None:
    write_project(vault, "broken", core=["methodology/missing-piece"])
    report = validate(vault)
    assert report["ok"] is False
    assert any(issue["kind"] == "missing_stanza" for issue in report["issues"])
    assert "findings" in report


def test_validate_fix_ignores_findings(vault: Path) -> None:
    write_stanza(vault, "methodology/orphan", "ORPHAN", title="Orphan")
    write_project(vault, "empty-harbor")
    fixed = validate(vault, fix=True)
    assert fixed["ok"] is True
    assert any(item["id"] == "methodology/orphan" for item in fixed["findings"]["unreferenced"])
    assert (vault / "stanzas" / "methodology" / "orphan.md").is_file()
    assert (vault / "projects" / "empty-harbor" / "map.yaml").is_file()


def test_affects_projects_on_map_role_global_and_stanza_update(vault: Path) -> None:
    write_stanza(vault, "interaction/voice", "VOICE", title="Voice")
    write_stanza(vault, "methodology/local", "LOCAL", title="Local")
    write_project(vault, "_global", core=["interaction/voice"])
    write_project(vault, "river-ledger")
    write_project(vault, "harbor-notes", include_global=False)

    created = create_stanza(
        vault,
        "methodology/new-piece",
        title="New",
        description="A new stanza",
        content="NEW",
        why="add unused stanza",
    )
    assert created["affects_projects"] == []

    linked = link_stanza(vault, "river-ledger", "methodology/local")
    assert linked["affects_projects"] == ["river-ledger"]

    global_link = link_stanza(vault, "_global", "methodology/local")
    assert "_global" in global_link["affects_projects"]
    assert "river-ledger" in global_link["affects_projects"]
    assert "harbor-notes" not in global_link["affects_projects"]

    updated = update_stanza(
        vault, "interaction/voice", content="VOICE-NEW", why="edit global voice"
    )
    assert "_global" in updated["affects_projects"]
    assert "river-ledger" in updated["affects_projects"]
    assert "harbor-notes" not in updated["affects_projects"]

    created_role = create_role(vault, "clerk")
    assert created_role["affects_projects"] == []


def test_delete_project_removes_directory_only(vault: Path) -> None:
    write_stanza(vault, "methodology/clerk-intake", "C")
    write_role(vault, "clerk", core=["methodology/clerk-intake"])
    write_project(vault, "harbor-notes", roles=["clerk"], notes="keep the role")
    preview = delete_project(vault, "harbor-notes")
    assert preview["ok"] is True
    assert preview["written"] is False
    assert "projects/harbor-notes/" in preview.get("statement", "") or "only" in preview.get(
        "statement", ""
    ).lower()

    result = delete_project(
        vault, "harbor-notes", confirm=True, expected=preview["expected"]
    )
    assert result["ok"] is True
    assert not (vault / "projects" / "harbor-notes").exists()
    assert (vault / "roles" / "clerk.yaml").is_file()
    assert (vault / "stanzas" / "methodology" / "clerk-intake.md").is_file()


def test_delete_role_confirm_strips_maps_and_frontmatter(vault: Path) -> None:
    write_stanza(
        vault,
        "methodology/clerk-intake",
        "C",
        extra_fm={"roles": ["clerk"]},
    )
    write_role(vault, "clerk", core=["methodology/clerk-intake"])
    write_project(vault, "river-ledger", roles=["clerk"], core=["methodology/clerk-intake"])
    preview = delete_role(vault, "clerk")
    result = delete_role(vault, "clerk", confirm=True, expected=preview["expected"])
    assert result["ok"] is True
    assert not (vault / "roles" / "clerk.yaml").is_file()
    river = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert "clerk" not in river.get("roles", [])
    assert river["core"] == ["methodology/clerk-intake"]
    loaded = load_vault(vault)
    assert "clerk" not in loaded.stanzas["methodology/clerk-intake"].roles


def test_update_role_name_writes_now(vault: Path) -> None:
    write_role(vault, "clerk", name="Old")
    result = update_role(vault, "clerk", name="Clerk")
    assert result["ok"] is True
    assert result.get("written") is not False
    data = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert data["name"] == "Clerk"


def test_delete_requires_expected_on_confirm(vault: Path) -> None:
    write_stanza(vault, "methodology/orphan", "O")
    result = delete_stanza(vault, "methodology/orphan", why="x", confirm=True)
    assert result["error"] == "missing_expected"


def test_create_role_already_exists(vault: Path) -> None:
    write_role(vault, "clerk")
    result = create_role(vault, "clerk")
    assert result["error"] == "already_exists"


@pytest.mark.skipif(GIT is None, reason="git not available")
def test_review_stages_bundled_delete_auto_commits_once(vault: Path) -> None:
    _seed_linked(vault)
    _init_git(vault)

    preview = delete_stanza(vault, "methodology/clerk-intake", why="bundle delete")
    reviewed = delete_stanza(
        vault,
        "methodology/clerk-intake",
        why="bundle delete",
        confirm=True,
        expected=preview["expected"],
    )
    assert reviewed["review"] == "review"
    assert reviewed["committed"] is False
    staged = _git(vault, "diff", "--cached", "--name-only")
    names = {line.replace("\\", "/") for line in staged.stdout.splitlines() if line}
    assert "stanzas/methodology/clerk-intake.md" in names
    assert "roles/clerk.yaml" in names
    assert "projects/river-ledger/map.yaml" in names
    head = _git(vault, "log", "-1", "--pretty=%s")
    assert "seed" in head.stdout
    _git(vault, "commit", "-m", "accept review delete")

    (vault / "config" / "review-policy.yaml").write_text("default: auto\n", encoding="utf-8")
    _git(vault, "add", "config/review-policy.yaml")
    _git(vault, "commit", "-m", "policy")

    preview2 = delete_stanza(vault, "methodology/orphan", why="auto delete")
    auto = delete_stanza(
        vault,
        "methodology/orphan",
        why="auto delete",
        confirm=True,
        expected=preview2["expected"],
    )
    assert auto["review"] == "auto"
    assert auto["committed"] is True
    head = _git(vault, "log", "-1", "--pretty=%s")
    assert "delete stanza methodology/orphan" in head.stdout
    log = _git(vault, "log", "--oneline")
    assert log.stdout.count("\n") >= 2
