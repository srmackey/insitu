"""Read tools over a vault: list/get stanzas and projects, where_used."""

from __future__ import annotations

from pathlib import Path

from insitu.identity import (
    GLOBAL_PROJECT,
    InvalidIdentity,
    validate_project_key,
    validate_role_id,
    validate_skill_id,
    validate_stanza_id,
)
from insitu.library import concrete_version, record_member_ids
from insitu.models import Vault
from insitu.resolve import (
    expand_import_field,
    expand_import_skills,
    first_wins,
    resolve_protocol,
)
from insitu.size import size_fields, total_size
from insitu.store import load_vault


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def _identity_error(value: str, exc: InvalidIdentity) -> dict:
    return {
        "ok": False,
        "error": "invalid_identity",
        "value": value,
        "reason": str(exc),
    }


def _matches_prefix(stanza_id: str, prefix: str) -> bool:
    return stanza_id == prefix or stanza_id.startswith(prefix + "/")


def _stanza_index_row(stanza, origin: str = "native") -> dict:
    row = {
        "id": stanza.id,
        "title": stanza.title,
        "description": stanza.description,
        "tags": list(stanza.tags),
        "origin": origin,
    }
    row.update(size_fields(stanza.content))
    return row


def _role_member_row(vault: Vault, raw_id: str) -> dict:
    stanza = vault.stanzas.get(raw_id)
    if stanza is None:
        return {"id": raw_id}
    item = {
        "id": stanza.id,
        "title": stanza.title,
        "description": stanza.description,
    }
    item.update(size_fields(stanza.content))
    return item


def get_stanza(
    vault_or_root: Vault | Path | str,
    stanza_id: str,
    project: str | None = None,
) -> dict:
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    vault = _as_vault(vault_or_root)
    stanza = vault.stanzas.get(sid)
    if stanza is not None:
        row = _stanza_index_row(stanza, origin="native")
        row["ok"] = True
        row["content"] = stanza.content
        return row
    if project:
        try:
            key = validate_project_key(project)
        except InvalidIdentity as exc:
            return _identity_error(project, exc)
        proj = vault.projects.get(key)
        if proj is None:
            return {"ok": False, "error": "project_missing", "project": key}
        for record in proj.imports:
            resolved = concrete_version(vault, record)
            if isinstance(resolved, dict):
                continue
            pack = vault.library.get(record.pack, {}).get(resolved)
            if pack is None:
                continue
            members = record_member_ids(record, pack, "core")
            members += record_member_ids(record, pack, "on_demand")
            if sid in members and sid in pack.stanzas:
                found = pack.stanzas[sid]
                row = _stanza_index_row(
                    found, origin=f"library/{record.pack}@{resolved}"
                )
                row["ok"] = True
                row["content"] = found.content
                return row
    return {"ok": False, "error": "missing_stanza", "id": sid}


def list_stanzas(
    vault_or_root: Vault | Path | str,
    prefix: str | None = None,
    tag: str | None = None,
) -> dict:
    vault = _as_vault(vault_or_root)
    prefix_norm: str | None = None
    if prefix:
        trimmed = prefix.replace("\\", "/").rstrip("/")
        try:
            prefix_norm = validate_stanza_id(trimmed)
        except InvalidIdentity as exc:
            return _identity_error(prefix, exc)

    rows = []
    for sid in sorted(vault.stanzas):
        stanza = vault.stanzas[sid]
        if prefix_norm and not _matches_prefix(sid, prefix_norm):
            continue
        if tag and tag not in stanza.tags:
            continue
        rows.append(_stanza_index_row(stanza, origin="native"))
    for pack_id in sorted(vault.library):
        for version in sorted(vault.library[pack_id]):
            pack = vault.library[pack_id][version]
            origin = f"library/{pack_id}@{version}"
            for sid in sorted(pack.stanzas):
                stanza = pack.stanzas[sid]
                if prefix_norm and not _matches_prefix(sid, prefix_norm):
                    continue
                if tag and tag not in stanza.tags:
                    continue
                rows.append(_stanza_index_row(stanza, origin=origin))
    return {"ok": True, "stanzas": rows}


def get_project(vault_or_root: Vault | Path | str, project: str) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    vault = _as_vault(vault_or_root)
    resolved = resolve_protocol(vault, key)
    if not resolved["ok"]:
        return resolved
    proj = vault.projects[key]
    return {
        "ok": True,
        "project": proj.key,
        "repo": proj.repo,
        "name": proj.name,
        "aka": list(proj.aka),
        "roles": list(proj.roles),
        "imports": [item.as_dict() for item in proj.imports],
        "core": list(proj.core),
        "on_demand": list(proj.on_demand),
        "include_global": proj.include_global,
        "notes": proj.notes,
        "size": resolved["size"],
        "skills": list(proj.skills),
        "skills_size": resolved.get("skills_size"),
    }


def list_projects(vault_or_root: Vault | Path | str) -> dict:
    vault = _as_vault(vault_or_root)
    keys = []
    if "_global" in vault.projects:
        keys.append("_global")
    keys.extend(sorted(k for k in vault.projects if k != "_global"))
    rows = []
    for key in keys:
        proj = vault.projects[key]
        resolved = resolve_protocol(vault, key)
        row = {
            "project": key,
            "repo": proj.repo,
            "name": proj.name,
            "aka": list(proj.aka),
        }
        if resolved["ok"]:
            row["size"] = resolved["size"]
        else:
            row["size"] = None
            row["error"] = resolved.get("error")
            if "id" in resolved:
                row["id"] = resolved["id"]
        rows.append(row)
    return {"ok": True, "projects": rows}


def list_on_demand(vault_or_root: Vault | Path | str, project: str) -> dict:
    resolved = resolve_protocol(vault_or_root, project)
    if not resolved["ok"]:
        return resolved
    return {
        "ok": True,
        "project": resolved["project"],
        "on_demand": resolved["on_demand"],
    }


def where_used(vault_or_root: Vault | Path | str, stanza_id: str) -> dict:
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    vault = _as_vault(vault_or_root)
    used: list[dict] = []
    keys = []
    if GLOBAL_PROJECT in vault.projects:
        keys.append(GLOBAL_PROJECT)
    keys.extend(sorted(k for k in vault.projects if k != GLOBAL_PROJECT))
    for key in keys:
        proj = vault.projects[key]
        lists: list[str] = []
        if sid in proj.core:
            lists.append("core")
        if sid in proj.on_demand:
            lists.append("on_demand")
        for raw_role in proj.roles:
            try:
                rid = validate_role_id(raw_role)
            except InvalidIdentity:
                continue
            role = vault.roles.get(rid)
            if role is None:
                continue
            if sid in role.core or sid in role.on_demand:
                lists.append(f"role:{rid}")
        import_core = expand_import_field(vault, proj.imports, "core")
        import_on_demand = expand_import_field(vault, proj.imports, "on_demand")
        if not isinstance(import_core, dict):
            for member_id, pack in import_core:
                if member_id == sid:
                    label = f"import:{pack.pack_id}@{pack.version}"
                    if label not in lists:
                        lists.append(label)
        if not isinstance(import_on_demand, dict):
            for member_id, pack in import_on_demand:
                if member_id == sid:
                    label = f"import:{pack.pack_id}@{pack.version}"
                    if label not in lists:
                        lists.append(label)
        if lists:
            used.append({"project": key, "lists": lists})
    for rid in sorted(vault.roles):
        role = vault.roles[rid]
        lists = []
        if sid in role.core:
            lists.append("core")
        if sid in role.on_demand:
            lists.append("on_demand")
        if lists:
            used.append({"role": rid, "lists": lists})
    return {"ok": True, "id": sid, "used_by": used}


def list_roles(vault_or_root: Vault | Path | str) -> dict:
    vault = _as_vault(vault_or_root)
    rows = []
    for rid in sorted(vault.roles):
        role = vault.roles[rid]
        texts = []
        for member_id in first_wins(list(role.core)):
            stanza = vault.stanzas.get(member_id)
            if stanza is not None:
                texts.append(stanza.content)
        rows.append(
            {
                "id": rid,
                "name": role.name,
                "description": role.description,
                "core_count": len(role.core),
                "on_demand_count": len(role.on_demand),
                "size": total_size(texts),
            }
        )
    return {"ok": True, "roles": rows}


def get_role(vault_or_root: Vault | Path | str, role_id: str) -> dict:
    try:
        rid = validate_role_id(role_id)
    except InvalidIdentity as exc:
        return _identity_error(role_id, exc)
    vault = _as_vault(vault_or_root)
    role = vault.roles.get(rid)
    if role is None:
        return {"ok": False, "error": "missing_role", "id": rid}
    core_items = [_role_member_row(vault, member_id) for member_id in role.core]
    on_demand_items = [_role_member_row(vault, member_id) for member_id in role.on_demand]
    texts = []
    for member_id in first_wins(list(role.core)):
        stanza = vault.stanzas.get(member_id)
        if stanza is not None:
            texts.append(stanza.content)
    projects: list[str] = []
    if GLOBAL_PROJECT in vault.projects and rid in vault.projects[GLOBAL_PROJECT].roles:
        projects.append(GLOBAL_PROJECT)
    projects.extend(
        sorted(
            key
            for key, proj in vault.projects.items()
            if key != GLOBAL_PROJECT and rid in proj.roles
        )
    )
    return {
        "ok": True,
        "id": rid,
        "name": role.name,
        "description": role.description,
        "core": core_items,
        "on_demand": on_demand_items,
        "projects": projects,
        "size": total_size(texts),
    }


def _skill_index_row(
    skill, projects: list[str], *, origin: str | None = None
) -> dict:
    row = {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "projects": list(projects),
    }
    if origin is not None:
        row["origin"] = origin
    row.update(size_fields(skill.content))
    return row


def _projects_listing_skill(vault: Vault, skill_id: str) -> list[str]:
    found: list[str] = []
    keys = []
    if GLOBAL_PROJECT in vault.projects:
        keys.append(GLOBAL_PROJECT)
    keys.extend(sorted(k for k in vault.projects if k != GLOBAL_PROJECT))
    for key in keys:
        if skill_id in vault.projects[key].skills:
            found.append(key)
    return found


def list_skills(vault_or_root: Vault | Path | str, prefix: str | None = None) -> dict:
    vault = _as_vault(vault_or_root)
    prefix_norm: str | None = None
    if prefix:
        prefix_norm = prefix.replace("\\", "/").rstrip("/")
        if not prefix_norm:
            return _identity_error(prefix, InvalidIdentity("skill prefix is empty"))
    rows = []
    for sid in sorted(vault.skills):
        if prefix_norm and sid != prefix_norm and not sid.startswith(prefix_norm):
            continue
        skill = vault.skills[sid]
        rows.append(_skill_index_row(skill, _projects_listing_skill(vault, sid)))
    return {"ok": True, "skills": rows}


def get_skill(
    vault_or_root: Vault | Path | str,
    skill_id: str,
    project: str | None = None,
) -> dict:
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault = _as_vault(vault_or_root)
    skill = vault.skills.get(sid)
    if skill is not None:
        row = _skill_index_row(
            skill, _projects_listing_skill(vault, sid), origin="native"
        )
        row["ok"] = True
        row["content"] = skill.content
        row["frontmatter"] = dict(skill.frontmatter)
        row["payload"] = list(skill.payload)
        return row
    if project:
        try:
            key = validate_project_key(project)
        except InvalidIdentity as exc:
            return _identity_error(project, exc)
        proj = vault.projects.get(key)
        if proj is None:
            return {"ok": False, "error": "project_missing", "project": key}
        imported = expand_import_skills(vault, proj.imports)
        if isinstance(imported, dict):
            return imported
        for imported_id, pack in imported:
            if imported_id != sid:
                continue
            found = pack.skills.get(sid)
            if found is None:
                break
            row = _skill_index_row(
                found,
                _projects_listing_skill(vault, sid),
                origin=f"library/{pack.pack_id}@{pack.version}",
            )
            row["ok"] = True
            row["content"] = found.content
            row["frontmatter"] = dict(found.frontmatter)
            row["payload"] = list(found.payload)
            return row
    return {"ok": False, "error": "missing_skill", "id": sid}


def where_used_skill(vault_or_root: Vault | Path | str, skill_id: str) -> dict:
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault = _as_vault(vault_or_root)
    used = [
        {"project": key, "lists": ["skills"]}
        for key in _projects_listing_skill(vault, sid)
    ]
    return {"ok": True, "id": sid, "used_by": used}
