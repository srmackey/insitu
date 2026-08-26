"""FastMCP server. Tools are thin wrappers over the shipped functions."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from insitu.catalog import (
    get_project as get_project_fn,
    get_role as get_role_fn,
    get_skill as get_skill_fn,
    get_stanza as get_stanza_fn,
    list_on_demand as list_on_demand_fn,
    list_projects as list_projects_fn,
    list_roles as list_roles_fn,
    list_skills as list_skills_fn,
    list_stanzas as list_stanzas_fn,
    where_used as where_used_fn,
    where_used_skill as where_used_skill_fn,
)
from insitu.library import (
    fetch_pack as fetch_pack_fn,
    get_pack as get_pack_fn,
    install_capability as install_capability_fn,
    install_skill as install_skill_fn,
    install_stanza as install_stanza_fn,
    list_packs as list_packs_fn,
    remove_pack as remove_pack_fn,
    uninstall_capability as uninstall_capability_fn,
    uninstall_skill as uninstall_skill_fn,
    uninstall_stanza as uninstall_stanza_fn,
)
from insitu.materialize import materialize as materialize_fn
from insitu.mutate import (
    create_project as create_project_fn,
    create_role as create_role_fn,
    create_skill as create_skill_fn,
    create_stanza as create_stanza_fn,
    delete_project as delete_project_fn,
    delete_role as delete_role_fn,
    delete_skill as delete_skill_fn,
    delete_stanza as delete_stanza_fn,
    link_skill as link_skill_fn,
    link_stanza as link_stanza_fn,
    unlink_skill as unlink_skill_fn,
    unlink_stanza as unlink_stanza_fn,
    update_project as update_project_fn,
    update_role as update_role_fn,
    update_skill as update_skill_fn,
    update_stanza as update_stanza_fn,
)
from insitu.resolve import resolve_protocol as resolve_protocol_fn
from insitu.status import project_status as project_status_fn
from insitu.validate import validate as validate_fn
from insitu.vault import resolve_vault_root

INSTRUCTIONS = """\
Insitu stores reusable stanzas of standing guidance and project-mapped skills,
and composes a project protocol.

Project key is the working folder basename (projects/<folder>/). Session start is
resolve_protocol for inspect; materialize writes PROTOCOL.md plus host adapters
and mapped skill copies. Pull on-demand stanzas with get_stanza. list_stanzas
shows the catalog and sizes. list_skills is the skill catalog, not session start.
"""

mcp = FastMCP("Insitu", instructions=INSTRUCTIONS)

_process_vault: Path | None = None


def set_vault(path: str | Path) -> None:
    global _process_vault
    _process_vault = Path(path).resolve()


def current_vault() -> Path:
    if _process_vault is None:
        return resolve_vault_root()
    return _process_vault


@mcp.tool
def resolve_protocol(project: str) -> dict:
    """Return the composed protocol for a project: core bodies, on-demand index, size."""
    return resolve_protocol_fn(current_vault(), project)


@mcp.tool
def get_stanza(stanza_id: str, project: str | None = None) -> dict:
    """Return one stanza by id (path relative to stanzas/, no .md). Optional project looks through that map's imports."""
    return get_stanza_fn(current_vault(), stanza_id, project=project)


@mcp.tool
def list_stanzas(
    prefix: str | None = None, tag: str | None = None, role: str | None = None
) -> dict:
    """List stanzas with title, description, tags, roles, and size. Optional prefix, tag, or role filter."""
    return list_stanzas_fn(current_vault(), prefix=prefix, tag=tag, role=role)


@mcp.tool
def list_projects() -> dict:
    """List projects including _global, labels, and composed-protocol size summaries."""
    return list_projects_fn(current_vault())


@mcp.tool
def get_project(project: str) -> dict:
    """Return a project map, notes, roles, and protocol size summary without the protocol body."""
    return get_project_fn(current_vault(), project)


@mcp.tool
def project_status(working_folder: str, project: str | None = None) -> dict:
    """Folder inspect card: map, sourced core ids, size, on-demand ids, disk freshness. No stanza bodies. Inspect only."""
    return project_status_fn(current_vault(), working_folder, project=project)


@mcp.tool
def list_roles() -> dict:
    """List role packs with id, name, description, member counts, and composed core size."""
    return list_roles_fn(current_vault())


@mcp.tool
def get_role(role_id: str) -> dict:
    """Return one role file, member stanza metadata and sizes, and projects that include it."""
    return get_role_fn(current_vault(), role_id)


@mcp.tool
def list_on_demand(project: str) -> dict:
    """List on-demand stanzas associated with a project (id, title, description, size)."""
    return list_on_demand_fn(current_vault(), project)


@mcp.tool
def validate(fix: bool = False) -> dict:
    """Vault health check. Read-only unless fix=true. Issues fail ok; findings do not. Fixes follow the review dial and never consume findings."""
    return validate_fn(current_vault(), fix=fix)


@mcp.tool
def create_stanza(
    stanza_id: str,
    title: str,
    description: str,
    content: str,
    why: str,
    tags: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict:
    """Create a stanza and append a why-log entry. Does not link it to a project. Subject to review policy."""
    return create_stanza_fn(
        current_vault(),
        stanza_id,
        title=title,
        description=description,
        content=content,
        why=why,
        tags=tags,
        roles=roles,
    )


@mcp.tool
def update_stanza(
    stanza_id: str,
    why: str,
    title: str | None = None,
    description: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict:
    """Update a stanza, append a why-log entry, and return where_used. Subject to review policy."""
    return update_stanza_fn(
        current_vault(),
        stanza_id,
        why=why,
        title=title,
        description=description,
        content=content,
        tags=tags,
        roles=roles,
    )


@mcp.tool
def list_skills(prefix: str | None = None) -> dict:
    """List vault skills with name, description, size, and which projects list them. Not session start."""
    return list_skills_fn(current_vault(), prefix=prefix)


@mcp.tool
def get_skill(skill_id: str, project: str | None = None) -> dict:
    """Return one skill: frontmatter, body, size, and payload file list. Optional project looks through that map's pack skills."""
    return get_skill_fn(current_vault(), skill_id, project=project)


@mcp.tool
def link_skill(project: str, skill_id: str) -> dict:
    """Add a skill to a project's skills list. Writes now. Does not edit role files."""
    return link_skill_fn(current_vault(), project, skill_id)


@mcp.tool
def unlink_skill(project: str, skill_id: str) -> dict:
    """Remove a skill from a project's map. Writes now."""
    return unlink_skill_fn(current_vault(), project, skill_id)


@mcp.tool
def create_skill(
    skill_id: str,
    description: str,
    content: str,
    why: str | None = None,
) -> dict:
    """Create skills/<id>/SKILL.md. Does not auto-link. Optional why writes provenance/skills/<id>.md."""
    return create_skill_fn(
        current_vault(),
        skill_id,
        description=description,
        content=content,
        why=why,
    )


@mcp.tool
def update_skill(
    skill_id: str,
    description: str | None = None,
    content: str | None = None,
    why: str | None = None,
) -> dict:
    """Update SKILL.md frontmatter and/or body. Surfaces where_used and affects_projects."""
    return update_skill_fn(
        current_vault(),
        skill_id,
        description=description,
        content=content,
        why=why,
    )


@mcp.tool
def delete_skill(
    skill_id: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a skill. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this skill."""
    return delete_skill_fn(
        current_vault(),
        skill_id,
        confirm=confirm,
        expected=expected,
        why=why,
    )


@mcp.tool
def where_used_skill(skill_id: str) -> dict:
    """List project maps that include this skill. Roles never appear."""
    return where_used_skill_fn(current_vault(), skill_id)


@mcp.tool
def link_stanza(project: str, stanza_id: str, target: str = "core") -> dict:
    """Add a stanza to a project's core or on-demand list. Does not edit role files."""
    return link_stanza_fn(current_vault(), project, stanza_id, target=target)


@mcp.tool
def unlink_stanza(project: str, stanza_id: str) -> dict:
    """Remove a stanza from a project's map. Does not edit role files."""
    return unlink_stanza_fn(current_vault(), project, stanza_id)


@mcp.tool
def delete_stanza(
    stanza_id: str,
    why: str,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    """Delete a stanza. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this stanza. Findings are not a reason to delete."""
    return delete_stanza_fn(
        current_vault(), stanza_id, why=why, confirm=confirm, expected=expected
    )


@mcp.tool
def create_role(
    role_id: str,
    name: str | None = None,
    description: str | None = None,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    why: str | None = None,
) -> dict:
    """Create a role file. The new role is on no project. Optional why is for the git message only."""
    return create_role_fn(
        current_vault(),
        role_id,
        name=name,
        description=description,
        core=core,
        on_demand=on_demand,
        why=why,
    )


@mcp.tool
def update_role(
    role_id: str,
    name: str | None = None,
    description: str | None = None,
    add_core: list[str] | None = None,
    remove_core: list[str] | None = None,
    add_on_demand: list[str] | None = None,
    remove_on_demand: list[str] | None = None,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Update a role. Name/description write now. Member add/remove is preview unless confirm=true with the preview's expected."""
    return update_role_fn(
        current_vault(),
        role_id,
        name=name,
        description=description,
        add_core=add_core,
        remove_core=remove_core,
        add_on_demand=add_on_demand,
        remove_on_demand=remove_on_demand,
        confirm=confirm,
        expected=expected,
        why=why,
    )


@mcp.tool
def delete_role(
    role_id: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a role. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this role. Findings are not a reason to delete."""
    return delete_role_fn(
        current_vault(),
        role_id,
        confirm=confirm,
        expected=expected,
        why=why,
    )


@mcp.tool
def create_project(
    project: str,
    repo: str | None = None,
    name: str | None = None,
    aka: list[str] | None = None,
    roles: list[str] | None = None,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    include_global: bool | None = None,
    notes: str | None = None,
    skills: list[str] | None = None,
    why: str | None = None,
) -> dict:
    """Create a project map and optional notes. Creating _global when missing is allowed."""
    return create_project_fn(
        current_vault(),
        project,
        repo=repo,
        name=name,
        aka=aka,
        roles=roles,
        core=core,
        on_demand=on_demand,
        include_global=include_global,
        notes=notes,
        skills=skills,
        why=why,
    )


@mcp.tool
def update_project(
    project: str,
    repo: str | None = None,
    name: str | None = None,
    aka: list[str] | None = None,
    include_global: bool | None = None,
    notes: str | None = None,
    add_roles: list[str] | None = None,
    remove_roles: list[str] | None = None,
    add_core: list[str] | None = None,
    remove_core: list[str] | None = None,
    add_on_demand: list[str] | None = None,
    remove_on_demand: list[str] | None = None,
    add_skills: list[str] | None = None,
    remove_skills: list[str] | None = None,
    why: str | None = None,
) -> dict:
    """Incrementally update a project map. Attach/detach role writes immediately and reports members, weight, and affects_projects."""
    return update_project_fn(
        current_vault(),
        project,
        repo=repo,
        name=name,
        aka=aka,
        include_global=include_global,
        notes=notes,
        add_roles=add_roles,
        remove_roles=remove_roles,
        add_core=add_core,
        remove_core=remove_core,
        add_on_demand=add_on_demand,
        add_skills=add_skills,
        remove_skills=remove_skills,
        remove_on_demand=remove_on_demand,
        why=why,
    )


@mcp.tool
def delete_project(
    project: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a project directory. Preview unless confirm=true with the preview's expected. Cannot delete _global. Do not call unless the user explicitly asked to delete this project. Findings are not a reason to delete."""
    return delete_project_fn(
        current_vault(),
        project,
        confirm=confirm,
        expected=expected,
        why=why,
    )


@mcp.tool
def where_used(stanza_id: str) -> dict:
    """List every project map and role file that references a stanza."""
    return where_used_fn(current_vault(), stanza_id)


@mcp.tool
def materialize(working_folder: str, project: str | None = None) -> dict:
    """Write PROTOCOL.md and configured host adapters into the working folder."""
    return materialize_fn(current_vault(), working_folder, project=project)


@mcp.tool
def list_packs() -> dict:
    """Shelf inventory: pack ids, versions, which maps use which, unreferenced versions."""
    return list_packs_fn(current_vault())


@mcp.tool
def get_pack(pack: str) -> dict:
    """One pack id: versions on disk, members, and which maps pin it."""
    return get_pack_fn(current_vault(), pack)


@mcp.tool
def install_capability(project: str, pack: str, version: str) -> dict:
    """This project uses the whole pack at version or latest. Pull onto the shelf if needed."""
    return install_capability_fn(current_vault(), project, pack, version)


@mcp.tool
def install_stanza(
    project: str,
    stanza_id: str,
    version: str,
    pack: str | None = None,
) -> dict:
    """This project uses one stanza from a pack version. Pull onto the shelf if needed."""
    return install_stanza_fn(
        current_vault(), project, stanza_id, version, pack=pack
    )


@mcp.tool
def uninstall_capability(project: str, pack: str, version: str) -> dict:
    """Drop this map's whole-capability record. Shelf unchanged."""
    return uninstall_capability_fn(current_vault(), project, pack, version)


@mcp.tool
def uninstall_stanza(project: str, stanza_id: str, pack: str, version: str) -> dict:
    """Drop this stanza from this map's import record. Shelf unchanged."""
    return uninstall_stanza_fn(current_vault(), project, stanza_id, pack, version)


@mcp.tool
def install_skill(
    project: str,
    skill_id: str,
    version: str,
    pack: str | None = None,
) -> dict:
    """This project uses one skill from a pack version. Pull onto the shelf if needed. Does not copy into native skills/."""
    return install_skill_fn(
        current_vault(), project, skill_id, version, pack=pack
    )


@mcp.tool
def uninstall_skill(project: str, skill_id: str, pack: str, version: str) -> dict:
    """Drop this pack skill from this map's import record. Shelf unchanged."""
    return uninstall_skill_fn(current_vault(), project, skill_id, pack, version)


@mcp.tool
def fetch_pack(
    pack: str,
    version: str,
    repo: str | None = None,
    path: str | None = None,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    """Admin: seed library/<id>/<version>/. No map change. Confirm if refreshing changed bytes."""
    return fetch_pack_fn(
        current_vault(),
        pack,
        version,
        repo=repo,
        path=path,
        confirm=confirm,
        expected=expected,
    )


@mcp.tool
def remove_pack(
    pack: str,
    version: str | None = None,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    """Admin: preview then confirm. Remove a shelf version (or all versions of an id)."""
    return remove_pack_fn(
        current_vault(), pack, version, confirm=confirm, expected=expected
    )


def advertised_tool_names() -> list[str]:
    """Names registered on the live FastMCP instance."""
    import asyncio
    import inspect

    tools = mcp.list_tools()
    if inspect.isawaitable(tools):
        tools = asyncio.run(tools)
    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        if name:
            names.append(str(name))
        elif isinstance(tool, str):
            names.append(tool)
    if not names:
        raise RuntimeError("cannot inspect FastMCP tool registry")
    return sorted(names)


def run(*, cli_vault: str | Path | None = None) -> None:
    set_vault(resolve_vault_root(cli_vault=cli_vault))
    mcp.run()
