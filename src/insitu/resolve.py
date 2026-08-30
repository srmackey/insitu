"""Compose a project protocol from disk (DESIGN.md §8)."""

from __future__ import annotations

import re
from pathlib import Path

from insitu.identity import (
    GLOBAL_PROJECT,
    InvalidIdentity,
    validate_project_key,
    validate_role_id,
    validate_skill_id,
    validate_stanza_id,
)
from insitu.library import concrete_version, newer_than_pin, record_member_ids, sync_latest
from insitu.models import ImportRecord, PackVersion, Project, Skill, Stanza, Vault
from insitu.size import size_fields, total_size
from insitu.store import both_keys_present, load_vault


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def first_wins(*sequences: list[str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for sequence in sequences:
        for stanza_id in sequence:
            if stanza_id in seen:
                continue
            seen.add(stanza_id)
            ids.append(stanza_id)
    return ids


def compose_core_ids(global_core: list[str], project_core: list[str]) -> list[str]:
    return first_wins(global_core, project_core)


def expand_role_groups(
    vault: Vault, role_ids: list[str], field: str
) -> list[list[str]] | dict:
    """Per-role lists for one-level expand. Returns groups or an error dict."""
    groups: list[list[str]] = []
    for raw_id in role_ids:
        try:
            rid = validate_role_id(raw_id)
        except InvalidIdentity as exc:
            return _identity_error(raw_id, exc)
        role = vault.roles.get(rid)
        if role is None:
            return {"ok": False, "error": "missing_role", "id": rid}
        groups.append(list(getattr(role, field)))
    return groups


def expand_role_field(
    vault: Vault, role_ids: list[str], field: str
) -> list[str] | dict:
    """One-level expand of role core/on_demand. Returns ids or an error dict."""
    groups = expand_role_groups(vault, role_ids, field)
    if isinstance(groups, dict):
        return groups
    return first_wins(*groups)


def composed_global_core(vault: Vault) -> list[str] | dict:
    if GLOBAL_PROJECT not in vault.projects:
        return []
    global_proj = vault.projects[GLOBAL_PROJECT]
    expanded = expand_role_field(vault, global_proj.roles, "core")
    if isinstance(expanded, dict):
        return expanded
    return first_wins(expanded, global_proj.core)


def _identity_error(value: str, exc: InvalidIdentity) -> dict:
    return {
        "ok": False,
        "error": "invalid_identity",
        "value": value,
        "reason": str(exc),
    }


_LEADING_H1 = re.compile(r"\A\s*#[ \t]+[^\n]*\n?")


def composed_body(stanza: Stanza) -> str:
    """The stanza body as it appears in a composed protocol, always headed.

    The heading comes from frontmatter `title`, and a leading H1 already in
    the body is replaced rather than doubled. Composition joins bodies with a
    blank line, so a body that opened without a heading used to read as more
    prose under the stanza before it. There is no way to author that now.
    """
    body = _LEADING_H1.sub("", stanza.content or "", count=1).strip()
    heading = "# " + stanza.title.rstrip()
    if not body:
        return heading
    return heading + "\n\n" + body


def _core_item(stanza: Stanza) -> dict:
    content = composed_body(stanza)
    item = {
        "id": stanza.id,
        "title": stanza.title,
        "description": stanza.description,
        "tags": list(stanza.tags),
        "content": content,
    }
    item.update(size_fields(content))
    return item


def _on_demand_item(stanza: Stanza) -> dict:
    item = {
        "id": stanza.id,
        "title": stanza.title,
        "description": stanza.description,
    }
    item.update(size_fields(stanza.content))
    return item


def _lookup_stanza(
    vault: Vault, raw_id: str, pack: PackVersion | None = None
) -> dict | Stanza:
    try:
        stanza_id = validate_stanza_id(raw_id)
    except InvalidIdentity as exc:
        return _identity_error(raw_id, exc)
    if pack is not None:
        stanza = pack.stanzas.get(stanza_id)
        if stanza is None:
            return {
                "ok": False,
                "error": "missing_stanza",
                "id": stanza_id,
                "pack": pack.pack_id,
                "version": pack.version,
            }
        return stanza
    stanza = vault.stanzas.get(stanza_id)
    if stanza is None:
        return {"ok": False, "error": "missing_stanza", "id": stanza_id}
    return stanza


def expand_import_groups(
    vault: Vault, records: list[ImportRecord], field: str
) -> list[tuple[list[str], PackVersion]] | dict:
    groups: list[tuple[list[str], PackVersion]] = []
    seen: dict[str, str] = {}
    for record in records:
        resolved = concrete_version(vault, record)
        if isinstance(resolved, dict):
            if record.version != "latest":
                return {
                    "ok": False,
                    "error": "broken_pin",
                    "pack": record.pack,
                    "version": record.version,
                }
            return resolved
        pack = vault.library.get(record.pack, {}).get(resolved)
        if pack is None:
            return {
                "ok": False,
                "error": "broken_pin",
                "pack": record.pack,
                "version": resolved,
            }
        ids = record_member_ids(record, pack, field)
        for sid in ids:
            origin = f"{record.pack}@{resolved}"
            if sid in seen:
                return {
                    "ok": False,
                    "error": "duplicate_import_stanza",
                    "id": sid,
                    "pack": record.pack,
                    "version": resolved,
                }
            seen[sid] = origin
        groups.append((ids, pack))
    return groups


def expand_import_skills(
    vault: Vault, records: list[ImportRecord]
) -> list[tuple[str, PackVersion]] | dict:
    out: list[tuple[str, PackVersion]] = []
    seen: dict[str, str] = {}
    for record in records:
        if record.is_capability() or not record.skills:
            continue
        resolved = concrete_version(vault, record)
        if isinstance(resolved, dict):
            if record.version != "latest":
                return {
                    "ok": False,
                    "error": "broken_pin",
                    "pack": record.pack,
                    "version": record.version,
                }
            return resolved
        pack = vault.library.get(record.pack, {}).get(resolved)
        if pack is None:
            return {
                "ok": False,
                "error": "broken_pin",
                "pack": record.pack,
                "version": resolved,
            }
        for sid in record.skills:
            origin = f"{record.pack}@{resolved}"
            if sid in seen:
                return {
                    "ok": False,
                    "error": "duplicate_import_skill",
                    "id": sid,
                    "pack": record.pack,
                    "version": resolved,
                }
            seen[sid] = origin
            out.append((sid, pack))
    return out


def iter_composed_skills(vault: Vault, proj: Project) -> list[Skill] | dict:
    items: list[Skill] = []
    seen: set[str] = set()
    for raw_id in proj.skills:
        try:
            skill_id = validate_skill_id(raw_id)
        except InvalidIdentity as exc:
            return _identity_error(raw_id, exc)
        if skill_id in seen:
            continue
        skill = vault.skills.get(skill_id)
        if skill is None:
            return {"ok": False, "error": "missing_skill", "id": skill_id}
        seen.add(skill_id)
        items.append(skill)
    imported = expand_import_skills(vault, proj.imports)
    if isinstance(imported, dict):
        return imported
    for raw_id, pack in imported:
        try:
            skill_id = validate_skill_id(raw_id)
        except InvalidIdentity as exc:
            return _identity_error(raw_id, exc)
        if skill_id in seen:
            return {
                "ok": False,
                "error": "duplicate_import_skill",
                "id": skill_id,
                "pack": pack.pack_id,
                "version": pack.version,
            }
        skill = pack.skills.get(skill_id)
        if skill is None:
            return {
                "ok": False,
                "error": "missing_skill",
                "id": skill_id,
                "pack": pack.pack_id,
                "version": pack.version,
            }
        seen.add(skill_id)
        items.append(skill)
    return items


def expand_import_field(
    vault: Vault, records: list[ImportRecord], field: str
) -> list[tuple[str, PackVersion]] | dict:
    groups = expand_import_groups(vault, records, field)
    if isinstance(groups, dict):
        return groups
    out: list[tuple[str, PackVersion]] = []
    seen: set[str] = set()
    for ids, pack in groups:
        for sid in ids:
            if sid in seen:
                continue
            seen.add(sid)
            out.append((sid, pack))
    return out


def import_notices(vault: Vault, records: list[ImportRecord]) -> list[dict]:
    notices: list[dict] = []
    for record in records:
        if record.version == "latest":
            continue
        newer = newer_than_pin(vault, record.pack, record.version)
        if newer:
            notices.append(
                {"pack": record.pack, "pinned": record.version, "newer": newer}
            )
    return notices


def attributed_core_sources(vault: Vault, proj: Project) -> list[dict] | dict:
    """Winning core ids grouped by source. First-wins. Empty groups omitted."""
    include_global = False if proj.key == GLOBAL_PROJECT else proj.include_global
    seen: set[str] = set()
    groups: list[dict] = []

    def take(kind: str, ids: list[str], **extra: str) -> None:
        kept: list[str] = []
        for sid in ids:
            if sid in seen:
                continue
            seen.add(sid)
            kept.append(sid)
        if kept:
            row: dict = {"kind": kind, "stanzas": kept}
            row.update(extra)
            groups.append(row)

    if include_global:
        composed = composed_global_core(vault)
        if isinstance(composed, dict):
            return composed
        take("_global", composed)

    role_groups = expand_role_groups(vault, proj.roles, "core")
    if isinstance(role_groups, dict):
        return role_groups
    for rid, ids in zip(proj.roles, role_groups):
        take("role", first_wins(list(ids)), id=rid)

    import_groups = expand_import_groups(vault, proj.imports, "core")
    if isinstance(import_groups, dict):
        return import_groups
    for ids, pack in import_groups:
        take("import", list(ids), pack=pack.pack_id, version=pack.version)

    take("project", list(proj.core))
    return groups


def resolve_protocol(vault_or_root: Vault | Path | str, project: str) -> dict:
    """Compose core + on-demand index for a project key."""
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)

    vault = _as_vault(vault_or_root)
    if key not in vault.projects:
        return {
            "ok": False,
            "error": "project_missing",
            "project": key,
            "missing_path": str(vault.root / "projects" / key),
        }

    proj = vault.projects[key]
    both = _both_keys_error(vault, key)
    if both is not None:
        return both
    pulled = False
    for record in proj.imports:
        if record.version == "latest" and sync_latest(vault, record.pack):
            pulled = True
    if pulled:
        vault = load_vault(vault.root)
        proj = vault.projects[key]
    include_global = False if key == GLOBAL_PROJECT else proj.include_global
    global_core: list[str] = []
    if include_global:
        composed = composed_global_core(vault)
        if isinstance(composed, dict):
            return composed
        global_core = composed

    role_core = expand_role_field(vault, proj.roles, "core")
    if isinstance(role_core, dict):
        return role_core
    role_on_demand = expand_role_field(vault, proj.roles, "on_demand")
    if isinstance(role_on_demand, dict):
        return role_on_demand
    import_core = expand_import_field(vault, proj.imports, "core")
    if isinstance(import_core, dict):
        return import_core
    import_on_demand = expand_import_field(vault, proj.imports, "on_demand")
    if isinstance(import_on_demand, dict):
        return import_on_demand

    core_items: list[dict] = []
    seen_core: set[str] = set()
    for raw_id in first_wins(global_core, role_core):
        found = _lookup_stanza(vault, raw_id)
        if isinstance(found, dict):
            return found
        core_items.append(_core_item(found))
        seen_core.add(found.id)
    for raw_id, pack in import_core:
        if raw_id in seen_core:
            continue
        found = _lookup_stanza(vault, raw_id, pack=pack)
        if isinstance(found, dict):
            return found
        core_items.append(_core_item(found))
        seen_core.add(found.id)
    for raw_id in first_wins(list(proj.core)):
        if raw_id in seen_core:
            continue
        found = _lookup_stanza(vault, raw_id)
        if isinstance(found, dict):
            return found
        core_items.append(_core_item(found))
        seen_core.add(found.id)

    composed_skills = iter_composed_skills(vault, proj)
    if isinstance(composed_skills, dict):
        return composed_skills
    skill_items: list[dict] = []
    for skill in composed_skills:
        item = {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
        }
        item.update(size_fields(skill.content))
        skill_items.append(item)

    on_demand_items: list[dict] = []
    seen_on_demand: set[str] = set()
    for raw_id in first_wins(role_on_demand):
        found = _lookup_stanza(vault, raw_id)
        if isinstance(found, dict):
            return found
        on_demand_items.append(_on_demand_item(found))
        seen_on_demand.add(found.id)
    for raw_id, pack in import_on_demand:
        if raw_id in seen_on_demand:
            continue
        found = _lookup_stanza(vault, raw_id, pack=pack)
        if isinstance(found, dict):
            return found
        on_demand_items.append(_on_demand_item(found))
        seen_on_demand.add(found.id)
    for raw_id in first_wins(list(proj.on_demand)):
        if raw_id in seen_on_demand:
            continue
        found = _lookup_stanza(vault, raw_id)
        if isinstance(found, dict):
            return found
        on_demand_items.append(_on_demand_item(found))
        seen_on_demand.add(found.id)

    skills_size = total_size([skill.content for skill in composed_skills])
    skills_size["count"] = skills_size.pop("stanza_count")

    return {
        "ok": True,
        "project": key,
        "include_global": include_global,
        "roles": list(proj.roles),
        "size": total_size([item["content"] for item in core_items]),
        "core": core_items,
        "on_demand": on_demand_items,
        "skills": skill_items,
        "skills_size": skills_size,
        "newer_available": import_notices(vault, proj.imports),
    }


def _both_keys_error(vault: Vault, project: str) -> dict | None:
    if GLOBAL_PROJECT in vault.projects:
        global_proj = vault.projects[GLOBAL_PROJECT]
        if both_keys_present(global_proj.raw):
            return {
                "ok": False,
                "error": "both_keys_present",
                "project": GLOBAL_PROJECT,
            }
        for raw_role in global_proj.roles:
            role = vault.roles.get(raw_role)
            if role is not None and both_keys_present(role.raw):
                return {"ok": False, "error": "both_keys_present", "role": role.id}
    proj = vault.projects[project]
    if both_keys_present(proj.raw):
        return {"ok": False, "error": "both_keys_present", "project": project}
    for raw_role in proj.roles:
        role = vault.roles.get(raw_role)
        if role is not None and both_keys_present(role.raw):
            return {"ok": False, "error": "both_keys_present", "role": role.id}
    return None
