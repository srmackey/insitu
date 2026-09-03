"""Insitu 0.8: available becomes on-demand."""

from __future__ import annotations

from pathlib import Path

import yaml

from insitu.catalog import get_project, get_role, list_on_demand, list_roles, where_used
from insitu.mutate import link_article, update_project, update_role
from insitu.resolve import resolve_protocol
from insitu.server import advertised_tool_names
from insitu.validate import validate
from helpers import write_project, write_role, write_article

ROOT = Path(__file__).resolve().parents[1]


def _dump_map(vault: Path, key: str, data: dict) -> None:
    folder = vault / "projects" / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "map.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _dump_role(vault: Path, role_id: str, data: dict) -> None:
    folder = vault / "roles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{role_id}.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def test_legacy_available_map_resolves_as_on_demand_without_write(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    _dump_map(
        vault,
        "river-ledger",
        {"core": [], "available": ["methodology/small-diffs"]},
    )
    before = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    result = resolve_protocol(vault, "river-ledger")
    after = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    assert result["ok"] is True
    assert "available" not in result
    assert [row["id"] for row in result["on_demand"]] == ["methodology/small-diffs"]
    assert "content" not in result["on_demand"][0]
    assert after == before
    assert "available:" in before


def test_on_demand_map_resolves() -> None:
    examples = ROOT / "examples" / "vault"
    result = resolve_protocol(examples, "river-ledger")
    assert result["ok"] is True
    assert "available" not in result
    assert all("content" not in row for row in result["on_demand"])


def test_both_keys_present_is_issue(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_article(vault, "methodology/other", "OTHER", title="Other")
    _dump_map(
        vault,
        "river-ledger",
        {
            "core": [],
            "available": ["methodology/small-diffs"],
            "on_demand": ["methodology/other"],
        },
    )
    resolved = resolve_protocol(vault, "river-ledger")
    assert resolved["ok"] is False
    assert resolved["error"] == "both_keys_present"
    report = validate(vault)
    assert report["ok"] is False
    assert any(item["kind"] == "both_keys_present" for item in report["issues"])
    assert report["findings"].get("legacy_available_key") in ([], None) or not any(
        item.get("project") == "river-ledger"
        for item in report["findings"].get("legacy_available_key", [])
    )


def test_link_article_on_demand_writes_new_key_and_drops_legacy(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_article(vault, "interaction/how-i-work-with-ai", "HOW", title="How")
    _dump_map(
        vault,
        "river-ledger",
        {"core": [], "available": ["interaction/how-i-work-with-ai"]},
    )
    linked = link_article(
        vault, "river-ledger", "methodology/small-diffs", target="on_demand"
    )
    assert linked["ok"] is True
    assert linked["target"] == "on_demand"
    assert "available" not in linked
    assert linked["on_demand"] == [
        "interaction/how-i-work-with-ai",
        "methodology/small-diffs",
    ]
    data = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert "available" not in data
    assert data["on_demand"] == [
        "interaction/how-i-work-with-ai",
        "methodology/small-diffs",
    ]


def test_link_article_target_available_is_invalid(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_project(vault, "river-ledger")
    before = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    result = link_article(
        vault, "river-ledger", "methodology/small-diffs", target="available"
    )
    after = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    assert result == {"ok": False, "error": "invalid_target", "value": "available"}
    assert after == before


def test_list_on_demand_is_index_without_content(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    _dump_map(
        vault,
        "river-ledger",
        {"core": [], "on_demand": ["methodology/small-diffs"]},
    )
    result = list_on_demand(vault, "river-ledger")
    assert result["ok"] is True
    assert [row["id"] for row in result["on_demand"]] == ["methodology/small-diffs"]
    assert "content" not in result["on_demand"][0]
    assert "available" not in result


def test_list_available_is_not_exported() -> None:
    names = set(advertised_tool_names())
    assert "list_on_demand" in names
    assert "list_available" not in names
    import insitu

    assert not hasattr(insitu, "list_available")
    assert hasattr(insitu, "list_on_demand")


def test_where_used_lists_on_demand(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    _dump_map(
        vault,
        "river-ledger",
        {"core": [], "on_demand": ["methodology/small-diffs"]},
    )
    used = where_used(vault, "methodology/small-diffs")
    assert used["used_by"] == [{"project": "river-ledger", "lists": ["on_demand"]}]


def test_update_project_and_role_use_on_demand_names(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_article(vault, "methodology/ledger-clerk", "CLERK", title="Clerk")
    write_role(vault, "clerk", name="Clerk", core=["methodology/ledger-clerk"])
    write_project(vault, "river-ledger", roles=["clerk"], core=[])
    added = update_project(
        vault, "river-ledger", add_on_demand=["methodology/small-diffs"]
    )
    assert added["ok"] is True
    assert "available" not in added
    assert added["on_demand"] == ["methodology/small-diffs"]
    preview = update_role(vault, "clerk", add_on_demand=["methodology/small-diffs"])
    assert preview["ok"] is True
    assert preview.get("written") is not True
    assert "add_on_demand" in preview["expected"]
    assert "add_available" not in preview["expected"]
    confirmed = update_role(
        vault,
        "clerk",
        add_on_demand=["methodology/small-diffs"],
        confirm=True,
        expected=preview["expected"],
    )
    assert confirmed["ok"] is True
    role_data = yaml.safe_load((vault / "roles" / "clerk.yaml").read_text(encoding="utf-8"))
    assert "available" not in role_data
    assert role_data["on_demand"] == ["methodology/small-diffs"]


def test_legacy_available_is_finding_and_fix_rewrites(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    _dump_map(
        vault,
        "river-ledger",
        {"core": [], "available": ["methodology/small-diffs"]},
    )
    report = validate(vault)
    assert report["ok"] is True
    findings = {item["project"] for item in report["findings"]["legacy_available_key"]}
    assert "river-ledger" in findings
    fixed = validate(vault, fix=True)
    assert fixed["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    )
    assert "available" not in data
    assert data["on_demand"] == ["methodology/small-diffs"]
    after = validate(vault)
    assert after["ok"] is True
    assert after["findings"]["legacy_available_key"] == []


def test_fix_does_not_guess_both_keys(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_article(vault, "methodology/other", "OTHER", title="Other")
    _dump_map(
        vault,
        "river-ledger",
        {
            "core": [],
            "available": ["methodology/small-diffs"],
            "on_demand": ["methodology/other"],
        },
    )
    before = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    fixed = validate(vault, fix=True)
    after = (vault / "projects" / "river-ledger" / "map.yaml").read_text(encoding="utf-8")
    assert fixed["ok"] is False
    assert any(item["kind"] == "both_keys_present" for item in fixed["issues"])
    assert after == before


def test_global_on_demand_is_not_in_a_protocol(vault: Path) -> None:
    write_article(vault, "interaction/global-avail", "GAVAIL", title="Global on-demand")
    write_project(vault, "_global", on_demand=["interaction/global-avail"])
    write_project(vault, "empty-harbor")
    report = validate(vault)
    assert report["ok"] is True
    empty_projects = {item["id"] for item in report["findings"]["empty_projects"]}
    assert "empty-harbor" in empty_projects
    assert "_global" not in empty_projects
    not_in = {item["id"] for item in report["findings"]["not_in_any_protocol"]}
    assert "interaction/global-avail" in not_in
    unreferenced = {item["id"] for item in report["findings"]["unreferenced"]}
    assert "interaction/global-avail" not in unreferenced


def test_get_project_and_role_use_on_demand_fields(vault: Path) -> None:
    write_article(vault, "methodology/small-diffs", "SMALL", title="Small diffs")
    write_role(
        vault, "clerk", name="Clerk", on_demand=["methodology/small-diffs"]
    )
    write_project(
        vault, "river-ledger", roles=["clerk"], on_demand=["methodology/small-diffs"]
    )
    proj = get_project(vault, "river-ledger")
    assert proj["ok"] is True
    assert proj["on_demand"] == ["methodology/small-diffs"]
    assert "available" not in proj
    role = get_role(vault, "clerk")
    assert [item["id"] for item in role["on_demand"]] == ["methodology/small-diffs"]
    assert "available" not in role
    listed = list_roles(vault)
    clerk = next(row for row in listed["roles"] if row["id"] == "clerk")
    assert clerk["on_demand_count"] == 1
    assert "available_count" not in clerk


def test_routers_and_install_use_on_demand_prose() -> None:
    routers = ROOT / "install" / "routers"
    texts = [
        (routers / "claude.md").read_text(encoding="utf-8"),
        (routers / "cursor.mdc").read_text(encoding="utf-8"),
        (routers / "grok.md").read_text(encoding="utf-8"),
        (ROOT / "install" / "AGENTS.md").read_text(encoding="utf-8"),
    ]
    for text in texts:
        assert "on-demand" in text
        assert "list_available" not in text
        assert "Pull `available`" not in text
