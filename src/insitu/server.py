"""FastMCP server. Tools are thin wrappers over the shipped functions."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from insitu.catalog import (
    get_project as get_project_fn,
    get_role as get_role_fn,
    get_skill as get_skill_fn,
    get_article as get_article_fn,
    list_on_demand as list_on_demand_fn,
    list_projects as list_projects_fn,
    list_roles as list_roles_fn,
    list_skills as list_skills_fn,
    list_articles as list_articles_fn,
    where_used as where_used_fn,
    where_used_skill as where_used_skill_fn,
)
from insitu.library import (
    fetch_pack as fetch_pack_fn,
    get_pack as get_pack_fn,
    install_capability as install_capability_fn,
    install_skill as install_skill_fn,
    install_article as install_article_fn,
    list_packs as list_packs_fn,
    remove_pack as remove_pack_fn,
    uninstall_capability as uninstall_capability_fn,
    uninstall_skill as uninstall_skill_fn,
    uninstall_article as uninstall_article_fn,
)
from insitu.materialize import materialize as materialize_fn
from insitu.mutate import (
    create_project as create_project_fn,
    create_role as create_role_fn,
    create_skill as create_skill_fn,
    create_article as create_article_fn,
    delete_project as delete_project_fn,
    delete_role as delete_role_fn,
    delete_skill as delete_skill_fn,
    delete_article as delete_article_fn,
    link_skill as link_skill_fn,
    link_article as link_article_fn,
    unlink_skill as unlink_skill_fn,
    unlink_article as unlink_article_fn,
    update_project as update_project_fn,
    update_role as update_role_fn,
    update_skill as update_skill_fn,
    update_article as update_article_fn,
)
from insitu.resolve import resolve_protocol as resolve_protocol_fn
from insitu.status import project_status as project_status_fn
from insitu.validate import validate as validate_fn
from insitu.affects import (
    project_keys,
    projects_carrying_role,
    projects_composed_including,
    projects_listing_skill,
)
from insitu.operators import (
    chair_key,
    check_map_write,
    check_vault_write,
    operator_status,
)
from insitu.store import load_vault
from insitu.operators import grant as grant_fn
from insitu.operators import revoke as revoke_fn
from insitu.vault import resolve_vault_root

INSTRUCTIONS = """\
Insitu stores reusable articles of standing guidance and project-mapped skills,
and composes a project protocol.

Project key is the working folder basename (projects/<folder>/). Session start is
resolve_protocol for inspect; materialize writes PROTOCOL.md plus host adapters
and mapped skill copies. Pull on-demand articles with get_article. list_articles
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


def _gated(project: str, working_folder: str, run) -> dict:
    """Run a mutating map write behind the operator gate.

    A bound chair may only write its own map, in its own folder. An admin
    chair may name any project. A vault with no operators.yaml is pre-init:
    the write proceeds and the result carries the warning.
    """
    refusal, warning = check_map_write(
        current_vault(), project=project, working_folder=working_folder
    )
    if refusal is not None:
        return refusal
    result = run()
    if warning and isinstance(result, dict) and result.get("ok"):
        result.setdefault("warning", warning)
    return result


# MCP tool annotations: host permission UI and directory listings read these.
# A hint that disagrees with the handler is worse than no hint, so they are
# grouped by what the handler actually does. Nothing here reaches the network:
# every tool is the local vault plus the working folder.
READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
# create_* refuses an existing object, so a repeat call is not a no-op.
WRITE_NEW = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}
# Repeating one of these with the same arguments writes nothing.
WRITE_IDEMPOTENT = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
DESTRUCTIVE = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _vault_gated(
    working_folder: str,
    *,
    kind: str,
    object_id: str,
    used_by: list[str],
    run,
) -> dict:
    """Run a write to a shared vault object behind the reach gate.

    Articles, roles, and skills are not owned by one map. Authoring is open to
    every chair; changing something other maps already compose is not.
    """
    refusal, warning = check_vault_write(
        current_vault(),
        working_folder=working_folder,
        used_by=used_by,
        kind=kind,
        object_id=object_id,
    )
    if refusal is not None:
        return refusal
    result = run()
    if warning and isinstance(result, dict) and result.get("ok"):
        result.setdefault("warning", warning)
    return result


def _article_reach(article_id: str) -> list[str]:
    """Maps that compose this article, directly or through a role."""
    return projects_composed_including(load_vault(current_vault()), article_id)


def _role_reach(role_id: str) -> list[str]:
    return projects_carrying_role(load_vault(current_vault()), role_id)


def _skill_reach(skill_id: str) -> list[str]:
    return projects_listing_skill(load_vault(current_vault()), skill_id)


@mcp.tool(annotations=READ_ONLY)
def resolve_protocol(project: str) -> dict:
    """Return the composed protocol for a project: core bodies, on-demand index, size."""
    return resolve_protocol_fn(current_vault(), project)


@mcp.tool(annotations=READ_ONLY)
def get_article(article_id: str, project: str | None = None) -> dict:
    """Return one article by id (path relative to articles/, no .md). Optional project looks through that map's imports."""
    return get_article_fn(current_vault(), article_id, project=project)


@mcp.tool(annotations=READ_ONLY)
def list_articles(prefix: str | None = None, tag: str | None = None) -> dict:
    """List articles with title, description, tags, and size. Optional prefix or tag filter. Role membership lives in the role file: use get_role."""
    return list_articles_fn(current_vault(), prefix=prefix, tag=tag)


@mcp.tool(annotations=READ_ONLY)
def list_projects() -> dict:
    """List projects including _global, labels, and composed-protocol size summaries."""
    return list_projects_fn(current_vault())


@mcp.tool(annotations=READ_ONLY)
def get_project(project: str) -> dict:
    """Return a project map, notes, roles, and protocol size summary without the protocol body."""
    return get_project_fn(current_vault(), project)


@mcp.tool(annotations=READ_ONLY)
def project_status(working_folder: str, project: str | None = None) -> dict:
    """Folder inspect card: map, sourced core ids, size, on-demand ids, disk freshness. No article bodies. Inspect only."""
    return project_status_fn(current_vault(), working_folder, project=project)


@mcp.tool(annotations=READ_ONLY)
def list_roles() -> dict:
    """List role packs with id, name, description, member counts, and composed core size."""
    return list_roles_fn(current_vault())


@mcp.tool(annotations=READ_ONLY)
def get_role(role_id: str) -> dict:
    """Return one role file, member article metadata and sizes, and projects that include it."""
    return get_role_fn(current_vault(), role_id)


@mcp.tool(annotations=READ_ONLY)
def list_on_demand(project: str) -> dict:
    """List on-demand articles associated with a project (id, title, description, size)."""
    return list_on_demand_fn(current_vault(), project)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def validate(working_folder: str, fix: bool = False) -> dict:
    """Vault health check. Read-only unless fix=true. Issues fail ok; findings do not. Fixes report the files they wrote and never consume findings. A fix rewrites shared vault files, so it needs admin unless this chair is the only map."""
    if not fix:
        return validate_fn(current_vault(), fix=False)
    return _vault_gated(
        working_folder,
        kind="vault",
        object_id="*",
        used_by=project_keys(load_vault(current_vault())),
        run=lambda: validate_fn(current_vault(), fix=True),
    )


@mcp.tool(annotations=WRITE_NEW)
def create_article(
    working_folder: str,
    article_id: str,
    title: str,
    description: str,
    content: str,
    why: str,
    tags: list[str] | None = None,
) -> dict:
    """Create an article and append a why-log entry. Does not link it to a project. Returns the files written. Authoring is open to any chair."""
    return _vault_gated(
        working_folder,
        kind="article",
        object_id=article_id,
        used_by=[],
        run=lambda: create_article_fn(
            current_vault(),
            article_id,
            title=title,
            description=description,
            content=content,
            why=why,
            tags=tags,
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def update_article(
    working_folder: str,
    article_id: str,
    why: str,
    title: str | None = None,
    description: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update an article, append a why-log entry, and return where_used. Returns the files written. Needs admin once a map other than this chair composes it."""
    return _vault_gated(
        working_folder,
        kind="article",
        object_id=article_id,
        used_by=_article_reach(article_id),
        run=lambda: update_article_fn(
            current_vault(),
            article_id,
            why=why,
            title=title,
            description=description,
            content=content,
            tags=tags,
        ),
    )


@mcp.tool(annotations=READ_ONLY)
def list_skills(prefix: str | None = None) -> dict:
    """List vault skills with name, description, size, and which projects list them. Not session start."""
    return list_skills_fn(current_vault(), prefix=prefix)


@mcp.tool(annotations=READ_ONLY)
def get_skill(skill_id: str, project: str | None = None) -> dict:
    """Return one skill: frontmatter, body, size, and payload file list. Optional project looks through that map's pack skills."""
    return get_skill_fn(current_vault(), skill_id, project=project)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def link_skill(working_folder: str, project: str, skill_id: str) -> dict:
    """Add a skill to a project's skills list. Writes now. Does not edit role files."""
    return _gated(
        project,
        working_folder,
        lambda: link_skill_fn(current_vault(), project, skill_id),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def unlink_skill(working_folder: str, project: str, skill_id: str) -> dict:
    """Remove a skill from a project's map. Writes now."""
    return _gated(
        project,
        working_folder,
        lambda: unlink_skill_fn(current_vault(), project, skill_id),
    )


@mcp.tool(annotations=WRITE_NEW)
def create_skill(
    working_folder: str,
    skill_id: str,
    description: str,
    content: str,
    why: str | None = None,
) -> dict:
    """Create skills/<id>/SKILL.md. Does not auto-link. Optional why writes provenance/skills/<id>.md."""
    return _vault_gated(
        working_folder,
        kind="skill",
        object_id=skill_id,
        used_by=[],
        run=lambda: create_skill_fn(
            current_vault(),
            skill_id,
            description=description,
            content=content,
            why=why,
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def update_skill(
    working_folder: str,
    skill_id: str,
    description: str | None = None,
    content: str | None = None,
    why: str | None = None,
) -> dict:
    """Update SKILL.md frontmatter and/or body. Surfaces where_used and affects_projects."""
    return _vault_gated(
        working_folder,
        kind="skill",
        object_id=skill_id,
        used_by=_skill_reach(skill_id),
        run=lambda: update_skill_fn(
            current_vault(),
            skill_id,
            description=description,
            content=content,
            why=why,
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_skill(
    working_folder: str,
    skill_id: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a skill. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this skill."""
    return _vault_gated(
        working_folder,
        kind="skill",
        object_id=skill_id,
        used_by=_skill_reach(skill_id),
        run=lambda: delete_skill_fn(
            current_vault(),
            skill_id,
            confirm=confirm,
            expected=expected,
            why=why,
        ),
    )


@mcp.tool(annotations=READ_ONLY)
def where_used_skill(skill_id: str) -> dict:
    """List project maps that include this skill. Roles never appear."""
    return where_used_skill_fn(current_vault(), skill_id)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def link_article(
    working_folder: str, project: str, article_id: str, target: str = "core"
) -> dict:
    """Add an article to a project's core or on-demand list. Does not edit role files."""
    return _gated(
        project,
        working_folder,
        lambda: link_article_fn(current_vault(), project, article_id, target=target),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def unlink_article(working_folder: str, project: str, article_id: str) -> dict:
    """Remove an article from a project's map. Does not edit role files."""
    return _gated(
        project,
        working_folder,
        lambda: unlink_article_fn(current_vault(), project, article_id),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_article(
    working_folder: str,
    article_id: str,
    why: str,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    """Delete an article. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this article. Findings are not a reason to delete."""
    return _vault_gated(
        working_folder,
        kind="article",
        object_id=article_id,
        used_by=_article_reach(article_id),
        run=lambda: delete_article_fn(
            current_vault(), article_id, why=why, confirm=confirm, expected=expected
        ),
    )


@mcp.tool(annotations=WRITE_NEW)
def create_role(
    working_folder: str,
    role_id: str,
    name: str | None = None,
    description: str | None = None,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    why: str | None = None,
) -> dict:
    """Create a role file. The new role is on no project, so authoring is open to any chair. Optional why writes a provenance entry."""
    return _vault_gated(
        working_folder,
        kind="role",
        object_id=role_id,
        used_by=[],
        run=lambda: create_role_fn(
            current_vault(),
            role_id,
            name=name,
            description=description,
            core=core,
            on_demand=on_demand,
            why=why,
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def update_role(
    working_folder: str,
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
    """Update a role. Name/description write now. Member add/remove is preview unless confirm=true with the preview's expected. A role reaches every map that carries it, so this needs admin once another map does."""
    return _vault_gated(
        working_folder,
        kind="role",
        object_id=role_id,
        used_by=_role_reach(role_id),
        run=lambda: update_role_fn(
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
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_role(
    working_folder: str,
    role_id: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a role. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this role. Findings are not a reason to delete."""
    return _vault_gated(
        working_folder,
        kind="role",
        object_id=role_id,
        used_by=_role_reach(role_id),
        run=lambda: delete_role_fn(
            current_vault(),
            role_id,
            confirm=confirm,
            expected=expected,
            why=why,
        ),
    )


@mcp.tool(annotations=WRITE_NEW)
def create_project(
    working_folder: str,
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
    return _gated(
        project,
        working_folder,
        lambda: create_project_fn(
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
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def update_project(
    working_folder: str,
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
    return _gated(
        project,
        working_folder,
        lambda: update_project_fn(
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
        ),
    )


@mcp.tool(annotations=DESTRUCTIVE)
def delete_project(
    working_folder: str,
    project: str,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    """Delete a project directory. Preview unless confirm=true with the preview's expected. Cannot delete _global. Do not call unless the user explicitly asked to delete this project. Findings are not a reason to delete."""
    return _gated(
        project,
        working_folder,
        lambda: delete_project_fn(
            current_vault(),
            project,
            confirm=confirm,
            expected=expected,
            why=why,
        ),
    )


@mcp.tool(annotations=READ_ONLY)
def operators() -> dict:
    """Inspect: operator classes, the registered admins, and the default class."""
    return operator_status(current_vault())


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def grant(working_folder: str, project: str, operator_class: str) -> dict:
    """Admin only: set a project's operator class to admin or bound."""
    return grant_fn(
        current_vault(),
        project=project,
        operator_class=operator_class,
        working_folder=working_folder,
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def revoke(working_folder: str, project: str) -> dict:
    """Admin only: drop a project back to the default class. Cannot revoke the last admin."""
    return revoke_fn(
        current_vault(), project=project, working_folder=working_folder
    )


@mcp.tool(annotations=READ_ONLY)
def where_used(article_id: str) -> dict:
    """List every project map and role file that references an article."""
    return where_used_fn(current_vault(), article_id)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def materialize(working_folder: str, project: str | None = None) -> dict:
    """Write PROTOCOL.md and configured host adapters into the working folder."""
    # No project named means this folder's own map, which the gate always
    # allows. Passing the raw path here would compare a path to a key.
    return _gated(
        project or chair_key(working_folder),
        working_folder,
        lambda: materialize_fn(current_vault(), working_folder, project=project),
    )


@mcp.tool(annotations=READ_ONLY)
def list_packs() -> dict:
    """Shelf inventory: pack ids, versions, which maps use which, unreferenced versions."""
    return list_packs_fn(current_vault())


@mcp.tool(annotations=READ_ONLY)
def get_pack(pack: str) -> dict:
    """One pack id: versions on disk, members, and which maps pin it."""
    return get_pack_fn(current_vault(), pack)


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def install_capability(
    working_folder: str, project: str, pack: str, version: str
) -> dict:
    """This project uses the whole pack at version or latest. Pull onto the shelf if needed."""
    return _gated(
        project,
        working_folder,
        lambda: install_capability_fn(current_vault(), project, pack, version),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def install_article(
    working_folder: str,
    project: str,
    article_id: str,
    version: str,
    pack: str | None = None,
    target: str = "core",
) -> dict:
    """This project uses one article from a pack version. Pull onto the shelf if needed. target is core or on_demand."""
    return _gated(
        project,
        working_folder,
        lambda: install_article_fn(
            current_vault(), project, article_id, version, pack=pack, target=target
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def uninstall_capability(
    working_folder: str, project: str, pack: str, version: str
) -> dict:
    """Drop this map's whole-capability record. Shelf unchanged."""
    return _gated(
        project,
        working_folder,
        lambda: uninstall_capability_fn(current_vault(), project, pack, version),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def uninstall_article(
    working_folder: str, project: str, article_id: str, pack: str, version: str
) -> dict:
    """Drop this article from this map's import record. Shelf unchanged."""
    return _gated(
        project,
        working_folder,
        lambda: uninstall_article_fn(
            current_vault(), project, article_id, pack, version
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def install_skill(
    working_folder: str,
    project: str,
    skill_id: str,
    version: str,
    pack: str | None = None,
) -> dict:
    """This project uses one skill from a pack version. Pull onto the shelf if needed. Does not copy into native skills/."""
    return _gated(
        project,
        working_folder,
        lambda: install_skill_fn(
            current_vault(), project, skill_id, version, pack=pack
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
def uninstall_skill(
    working_folder: str, project: str, skill_id: str, pack: str, version: str
) -> dict:
    """Drop this pack skill from this map's import record. Shelf unchanged."""
    return _gated(
        project,
        working_folder,
        lambda: uninstall_skill_fn(
            current_vault(), project, skill_id, pack, version
        ),
    )


@mcp.tool(annotations=WRITE_IDEMPOTENT)
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


@mcp.tool(annotations=DESTRUCTIVE)
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
