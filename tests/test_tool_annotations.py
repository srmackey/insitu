"""Every advertised tool carries the four MCP hints, and they match the handler.

Directory listings reject a tool whose hints are missing or non-boolean, and a
hint that disagrees with what the handler does is worse than no hint at all.
"""

from __future__ import annotations

import asyncio
import inspect

from insitu.server import mcp

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

READ_ONLY = {
    "resolve_protocol", "get_article", "list_articles", "list_projects", "get_project",
    "project_status", "list_roles", "get_role", "list_on_demand", "list_skills",
    "get_skill", "where_used_skill", "where_used", "operators", "list_packs", "get_pack",
}
DESTRUCTIVE = {
    "delete_skill", "delete_article", "delete_role", "delete_project", "remove_pack",
}
NOT_IDEMPOTENT = {"create_article", "create_skill", "create_role", "create_project"}


def _tools() -> dict:
    listed = mcp.list_tools()
    if inspect.isawaitable(listed):
        listed = asyncio.run(listed)
    return {tool.name: tool for tool in listed}


def test_every_tool_declares_all_four_hints_as_booleans() -> None:
    tools = _tools()
    assert tools
    for name, tool in tools.items():
        annotations = tool.annotations
        assert annotations is not None, f"{name} declares no annotations"
        for hint in HINTS:
            value = getattr(annotations, hint)
            assert isinstance(value, bool), f"{name}.{hint} is {value!r}, not a bool"


def test_read_only_hint_matches_whether_the_handler_writes() -> None:
    for name, tool in _tools().items():
        assert tool.annotations.readOnlyHint is (name in READ_ONLY), name


def test_only_deletes_are_marked_destructive() -> None:
    for name, tool in _tools().items():
        assert tool.annotations.destructiveHint is (name in DESTRUCTIVE), name


def test_create_tools_are_not_idempotent_and_the_rest_are() -> None:
    for name, tool in _tools().items():
        assert tool.annotations.idempotentHint is (name not in NOT_IDEMPOTENT), name


def test_nothing_is_open_world() -> None:
    # 0.14 removed every git call and every subprocess. fetch_pack resolves a
    # pack from a local path or a configured local source, never the network.
    for name, tool in _tools().items():
        assert tool.annotations.openWorldHint is False, name


def test_validate_is_not_read_only_because_fix_writes() -> None:
    validate = _tools()["validate"]
    assert validate.annotations.readOnlyHint is False
    assert validate.annotations.destructiveHint is False
