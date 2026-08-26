from __future__ import annotations

from insitu.server import advertised_tool_names


REQUIRED = {
    "resolve_protocol",
    "get_stanza",
    "list_stanzas",
    "list_projects",
    "get_project",
    "project_status",
    "list_roles",
    "get_role",
    "list_on_demand",
    "validate",
    "where_used",
    "materialize",
    "create_stanza",
    "update_stanza",
    "link_stanza",
    "unlink_stanza",
    "delete_stanza",
    "create_role",
    "update_role",
    "delete_role",
    "create_project",
    "update_project",
    "delete_project",
    "list_packs",
    "get_pack",
    "install_capability",
    "install_stanza",
    "install_skill",
    "uninstall_capability",
    "uninstall_stanza",
    "uninstall_skill",
    "fetch_pack",
    "remove_pack",
    "list_skills",
    "get_skill",
    "link_skill",
    "unlink_skill",
    "create_skill",
    "update_skill",
    "delete_skill",
    "where_used_skill",
}

ABSENT = {
    "rename_stanza",
    "rename_role",
    "rename_project",
    "rename_skill",
}


def test_mcp_surface_exposes_v1_and_0_6_tools_not_rename() -> None:
    names = set(advertised_tool_names())
    assert REQUIRED <= names
    assert names.isdisjoint(ABSENT)
