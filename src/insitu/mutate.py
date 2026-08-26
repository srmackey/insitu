"""Vault mutations: stanzas, roles, projects, and map links."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from insitu.affects import (
    affects_for_map_edit,
    expected_matches,
    project_keys,
    projects_composed_including,
    stanza_already_in_protocol,
)
from insitu.catalog import get_project, get_skill, get_stanza, where_used, where_used_skill
from insitu.identity import (
    GLOBAL_PROJECT,
    InvalidIdentity,
    validate_project_key,
    validate_role_id,
    validate_skill_id,
    validate_stanza_id,
)
from insitu.review import apply_review, load_review_policy
from insitu.size import size_fields
from insitu.store import load_vault, read_frontmatter


def _identity_error(value: str, exc: InvalidIdentity) -> dict:
    return {
        "ok": False,
        "error": "invalid_identity",
        "value": value,
        "reason": str(exc),
    }


def _today() -> str:
    return date.today().isoformat()


def _normalize_body(content: str) -> str:
    if content.startswith("\n"):
        content = content[1:]
    return content.rstrip("\n")


def _stanza_rel(stanza_id: str) -> Path:
    return Path(*stanza_id.split("/"))


def _stanza_md_path(vault_root: Path, stanza_id: str) -> Path:
    return vault_root / "stanzas" / _stanza_rel(stanza_id).with_suffix(".md")


def _why_log_path(vault_root: Path, stanza_id: str) -> Path:
    return vault_root / "provenance" / _stanza_rel(stanza_id).with_suffix(".md")


def _legacy_why_log_path(vault_root: Path, stanza_id: str) -> Path:
    rel = _stanza_rel(stanza_id)
    return vault_root / "stanzas" / rel.parent / f"{rel.name}.prov.md"


def _stanza_paths(vault_root: Path, stanza_id: str) -> tuple[Path, Path]:
    return _stanza_md_path(vault_root, stanza_id), _why_log_path(vault_root, stanza_id)


def _migrate_legacy_why_log(vault_root: Path, stanza_id: str) -> list[Path]:
    """Move or drop a leftover sibling .prov.md. Returns extra paths to stage."""
    dest = _why_log_path(vault_root, stanza_id)
    legacy = _legacy_why_log_path(vault_root, stanza_id)
    if not legacy.is_file():
        return []
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
    legacy.unlink()
    return [legacy]


def _dump_markdown(meta: dict[str, Any], body: str) -> str:
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n"
    body = body or ""
    if body and not body.startswith("\n"):
        text += "\n"
    text += body
    if not text.endswith("\n"):
        text += "\n"
    return text


def _append_why_log(path: Path, stanza_id: str, why: str) -> None:
    entry = f"## {_today()}\nWhy: {why}\n"
    if path.is_file():
        existing = path.read_text(encoding="utf-8").rstrip()
        path.write_text(existing + "\n\n" + entry, encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Provenance — {stanza_id}\n\n{entry}", encoding="utf-8")


def _clean_why(why: str | None) -> str | None:
    if why is None:
        return None
    stripped = why.strip()
    return stripped or None


def _review_message(action: str, why: str | None) -> str:
    if why:
        return f"insitu: {action}: {why}"
    return f"insitu: {action}"


def _write_map(
    folder: Path,
    raw: dict[str, Any],
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    *,
    roles: list[str] | None = None,
    skills: list[str] | None = None,
    repo: Any = None,
    name: Any = None,
    aka: Any = None,
    include_global: Any = None,
    set_repo: bool = False,
    set_name: bool = False,
    set_aka: bool = False,
    set_include_global: bool = False,
) -> Path:
    data = dict(raw)
    if core is not None:
        data["core"] = list(core)
    if on_demand is not None:
        data["on_demand"] = list(on_demand)
    data.pop("available", None)
    if roles is not None:
        data["roles"] = list(roles)
    if skills is not None:
        if skills:
            data["skills"] = list(skills)
        else:
            data.pop("skills", None)
    if set_repo:
        data["repo"] = repo
    if set_name:
        data["name"] = name
    if set_aka:
        data["aka"] = list(aka or [])
    if set_include_global:
        data["include_global"] = include_global
    path = folder / "map.yaml"
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _write_role_file(vault_root: Path, role_id: str, data: dict[str, Any]) -> Path:
    payload = dict(data)
    if "on_demand" not in payload and "available" in payload:
        payload["on_demand"] = list(payload.get("available") or [])
    payload.pop("available", None)
    folder = vault_root / "roles"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{role_id}.yaml"
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _frontmatter_roles(meta: dict[str, Any]) -> list[str]:
    roles = meta.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    return [str(item) for item in roles]


def _add_frontmatter_role(path: Path, role_id: str) -> None:
    post = read_frontmatter(path)
    meta = dict(post.metadata or {})
    roles = _frontmatter_roles(meta)
    if role_id not in roles:
        roles.append(role_id)
    meta["roles"] = roles
    path.write_text(_dump_markdown(meta, post.content or ""), encoding="utf-8")


def _remove_frontmatter_role(path: Path, role_id: str) -> None:
    post = read_frontmatter(path)
    meta = dict(post.metadata or {})
    roles = [item for item in _frontmatter_roles(meta) if item != role_id]
    if roles:
        meta["roles"] = roles
    else:
        meta.pop("roles", None)
    path.write_text(_dump_markdown(meta, post.content or ""), encoding="utf-8")


def _preview_gate(confirm: bool, expected: dict | None, plan: dict) -> dict | None:
    if not confirm:
        return {**plan, "ok": True, "written": False}
    if expected is None:
        return {"ok": False, "error": "missing_expected"}
    if not expected_matches(plan.get("expected", {}), expected):
        return {**plan, "ok": False, "error": "stale_preview", "written": False}
    return None


def _as_list(value: list[str] | None) -> list[str]:
    return list(value or [])


def create_stanza(
    vault_or_root: Path | str,
    stanza_id: str,
    *,
    title: str,
    description: str,
    content: str,
    why: str,
    tags: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict:
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    vault_root = Path(vault_or_root)
    reason = _clean_why(why)
    if reason is None:
        return {"ok": False, "error": "missing_why"}
    if not str(title).strip() or not str(description).strip():
        return {"ok": False, "error": "missing_frontmatter", "id": sid}
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    path, prov = _stanza_paths(vault_root, sid)
    if path.exists():
        return {"ok": False, "error": "stanza_exists", "id": sid}
    meta: dict[str, Any] = {
        "id": sid,
        "title": str(title).strip(),
        "description": str(description).strip(),
    }
    if tags:
        meta["tags"] = list(tags)
    if roles:
        meta["roles"] = list(roles)
    today = _today()
    meta["created"] = today
    meta["updated"] = today
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_markdown(meta, content or ""), encoding="utf-8")
    extra = _migrate_legacy_why_log(vault_root, sid)
    _append_why_log(prov, sid, reason)
    reviewed = apply_review(
        vault_root,
        [path, prov, *extra],
        f"insitu: create stanza {sid}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = get_stanza(vault_root, sid)
    result.update(reviewed)
    result["why_log"] = Path(prov).relative_to(vault_root).as_posix()
    result["affects_projects"] = []
    return result


def update_stanza(
    vault_or_root: Path | str,
    stanza_id: str,
    *,
    why: str,
    title: str | None = None,
    description: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict:
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    vault_root = Path(vault_or_root)
    reason = _clean_why(why)
    if reason is None:
        return {"ok": False, "error": "missing_why"}
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    stanza = vault.stanzas.get(sid)
    if stanza is None:
        return {"ok": False, "error": "missing_stanza", "id": sid}
    if all(value is None for value in (title, description, content, tags, roles)):
        return {"ok": False, "error": "no_changes", "id": sid}
    post = read_frontmatter(stanza.path)
    meta = dict(post.metadata or {})
    body = post.content or ""
    changed = False
    if title is not None and str(title).strip() != stanza.title:
        meta["title"] = str(title).strip()
        changed = True
    if description is not None and str(description).strip() != stanza.description:
        meta["description"] = str(description).strip()
        changed = True
    if tags is not None and list(tags) != list(stanza.tags):
        meta["tags"] = list(tags)
        changed = True
    if roles is not None and list(roles) != list(stanza.roles):
        meta["roles"] = list(roles)
        changed = True
    if content is not None and _normalize_body(content) != stanza.content:
        body = content
        changed = True
    if not changed:
        return {"ok": False, "error": "no_changes", "id": sid}
    meta["id"] = sid
    meta["updated"] = _today()
    if not meta.get("title") or not meta.get("description"):
        return {"ok": False, "error": "missing_frontmatter", "id": sid}
    used = where_used(vault_root, sid)
    affects = projects_composed_including(vault, sid)
    stanza.path.write_text(_dump_markdown(meta, body), encoding="utf-8")
    _, prov = _stanza_paths(vault_root, sid)
    extra = _migrate_legacy_why_log(vault_root, sid)
    _append_why_log(prov, sid, reason)
    reviewed = apply_review(
        vault_root,
        [stanza.path, prov, *extra],
        f"insitu: update stanza {sid}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = get_stanza(vault_root, sid)
    result.update(reviewed)
    result["where_used"] = used
    result["why_log"] = Path(prov).relative_to(vault_root).as_posix()
    result["affects_projects"] = affects
    return result


def link_stanza(
    vault_or_root: Path | str,
    project: str,
    stanza_id: str,
    *,
    target: str = "core",
) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    if target not in {"core", "on_demand"}:
        return {"ok": False, "error": "invalid_target", "value": target}
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "missing_project", "id": key}
    if sid not in vault.stanzas:
        return {"ok": False, "error": "missing_stanza", "id": sid}
    if sid in proj.core:
        return {"ok": False, "error": "already_linked", "id": sid, "target": "core", "project": key}
    if sid in proj.on_demand:
        return {
            "ok": False,
            "error": "already_linked",
            "id": sid,
            "target": "on_demand",
            "project": key,
        }
    core = list(proj.core)
    on_demand = list(proj.on_demand)
    if target == "core":
        core.append(sid)
    else:
        on_demand.append(sid)
    path = _write_map(proj.path, proj.raw, core, on_demand)
    reviewed = apply_review(
        vault_root,
        [path],
        f"insitu: link {sid} to {key} {target}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "project": key,
        "id": sid,
        "target": target,
        "core": core,
        "on_demand": on_demand,
        "affects_projects": affects_for_map_edit(vault, key),
    }
    result.update(reviewed)
    return result


def unlink_stanza(
    vault_or_root: Path | str,
    project: str,
    stanza_id: str,
) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "missing_project", "id": key}
    if sid not in proj.core and sid not in proj.on_demand:
        return {"ok": False, "error": "not_linked", "id": sid, "project": key}
    core = [item for item in proj.core if item != sid]
    on_demand = [item for item in proj.on_demand if item != sid]
    path = _write_map(proj.path, proj.raw, core, on_demand)
    reviewed = apply_review(
        vault_root,
        [path],
        f"insitu: unlink {sid} from {key}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "project": key,
        "id": sid,
        "core": core,
        "on_demand": on_demand,
        "affects_projects": affects_for_map_edit(vault, key),
    }
    result.update(reviewed)
    return result


def _skill_dir(vault_root: Path, skill_id: str) -> Path:
    return vault_root / "skills" / skill_id


def _skill_md_path(vault_root: Path, skill_id: str) -> Path:
    return _skill_dir(vault_root, skill_id) / "SKILL.md"


def _skill_why_log_path(vault_root: Path, skill_id: str) -> Path:
    return vault_root / "provenance" / "skills" / f"{skill_id}.md"


def _skill_frontmatter(
    skill_id: str,
    description: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": skill_id, "description": description}
    if extra:
        for key, value in extra.items():
            if key == "name":
                continue
            meta[key] = value
    return meta


def create_skill(
    vault_or_root: Path | str,
    skill_id: str,
    *,
    description: str,
    content: str,
    why: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault_root = Path(vault_or_root)
    if not str(description).strip():
        return {"ok": False, "error": "missing_frontmatter", "id": sid}
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    path = _skill_md_path(vault_root, sid)
    if path.exists():
        return {"ok": False, "error": "skill_exists", "id": sid}
    meta = _skill_frontmatter(sid, str(description).strip(), extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_markdown(meta, content or ""), encoding="utf-8")
    paths = [path]
    reason = _clean_why(why)
    if reason is not None:
        prov = _skill_why_log_path(vault_root, sid)
        _append_why_log(prov, sid, reason)
        paths.append(prov)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"create skill {sid}", reason),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = get_skill(vault_root, sid)
    result.update(reviewed)
    result["affects_projects"] = []
    if reason is not None:
        result["why_log"] = Path(_skill_why_log_path(vault_root, sid)).relative_to(
            vault_root
        ).as_posix()
    return result


def update_skill(
    vault_or_root: Path | str,
    skill_id: str,
    *,
    description: str | None = None,
    content: str | None = None,
    extra: dict[str, Any] | None = None,
    why: str | None = None,
) -> dict:
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    skill = vault.skills.get(sid)
    if skill is None:
        return {"ok": False, "error": "missing_skill", "id": sid}
    if description is None and content is None and extra is None:
        return {"ok": False, "error": "no_changes", "id": sid}
    post = read_frontmatter(skill.path)
    meta = dict(post.metadata or {})
    body = post.content or ""
    changed = False
    if description is not None and str(description).strip() != skill.description:
        meta["description"] = str(description).strip()
        changed = True
    if extra:
        for key, value in extra.items():
            if key == "name":
                if str(value) != sid:
                    return {
                        "ok": False,
                        "error": "skill_name_mismatch",
                        "id": sid,
                        "name": str(value),
                    }
                continue
            if meta.get(key) != value:
                meta[key] = value
                changed = True
    if content is not None and _normalize_body(content) != skill.content:
        body = content
        changed = True
    if not changed:
        return {"ok": False, "error": "no_changes", "id": sid}
    meta["name"] = sid
    if not meta.get("description"):
        return {"ok": False, "error": "missing_frontmatter", "id": sid}
    used = where_used_skill(vault_root, sid)
    affects = _projects_listing_skill(vault, sid)
    skill.path.write_text(_dump_markdown(meta, body), encoding="utf-8")
    paths = [skill.path]
    reason = _clean_why(why)
    if reason is not None:
        prov = _skill_why_log_path(vault_root, sid)
        _append_why_log(prov, sid, reason)
        paths.append(prov)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"update skill {sid}", reason),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = get_skill(vault_root, sid)
    result.update(reviewed)
    result["where_used"] = used
    result["affects_projects"] = affects
    return result


def _projects_listing_skill(vault, skill_id: str) -> list[str]:
    return [key for key in project_keys(vault) if skill_id in vault.projects[key].skills]


def link_skill(vault_or_root: Path | str, project: str, skill_id: str) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "missing_project", "id": key}
    if sid not in vault.skills:
        return {"ok": False, "error": "missing_skill", "id": sid}
    if sid in proj.skills:
        return {
            "ok": False,
            "error": "already_linked",
            "id": sid,
            "project": key,
        }
    skills = list(proj.skills)
    skills.append(sid)
    path = _write_map(proj.path, proj.raw, skills=skills)
    reviewed = apply_review(
        vault_root,
        [path],
        f"insitu: link skill {sid} to {key}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "project": key,
        "id": sid,
        "skills": skills,
        "affects_projects": affects_for_map_edit(vault, key),
    }
    result.update(reviewed)
    return result


def unlink_skill(vault_or_root: Path | str, project: str, skill_id: str) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "missing_project", "id": key}
    if sid not in proj.skills:
        return {"ok": False, "error": "not_linked", "id": sid, "project": key}
    skills = [item for item in proj.skills if item != sid]
    path = _write_map(proj.path, proj.raw, skills=skills)
    reviewed = apply_review(
        vault_root,
        [path],
        f"insitu: unlink skill {sid} from {key}",
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "project": key,
        "id": sid,
        "skills": skills,
        "affects_projects": affects_for_map_edit(vault, key),
    }
    result.update(reviewed)
    return result


def _skill_delete_plan(vault, sid: str) -> dict:
    skill = vault.skills[sid]
    projects = _projects_listing_skill(vault, sid)
    return {
        "id": sid,
        "name": skill.name,
        "size": size_fields(skill.content),
        "projects": projects,
        "expected": {"projects": list(projects)},
        "affects_projects": list(projects),
    }


def delete_skill(
    vault_or_root: Path | str,
    skill_id: str,
    *,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    try:
        sid = validate_skill_id(skill_id)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    if sid not in vault.skills:
        return {"ok": False, "error": "not_found", "id": sid}
    plan = _skill_delete_plan(vault, sid)
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated
    paths: list[Path] = []
    for key in plan["expected"]["projects"]:
        proj = vault.projects[key]
        skills = [item for item in proj.skills if item != sid]
        paths.append(_write_map(proj.path, proj.raw, skills=skills))
    folder = _skill_dir(vault_root, sid)
    if folder.is_dir():
        shutil.rmtree(folder)
        paths.append(folder)
    prov = _skill_why_log_path(vault_root, sid)
    if prov.is_file():
        prov.unlink()
        paths.append(prov)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"delete skill {sid}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {**plan, "ok": True, "written": True}
    result.update(reviewed)
    return result


def _stanza_delete_plan(vault, sid: str) -> dict:
    stanza = vault.stanzas[sid]
    role_core: list[str] = []
    role_on_demand: list[str] = []
    role_ids: list[str] = []
    for rid, role in sorted(vault.roles.items()):
        listed = False
        if sid in role.core:
            role_core.append(rid)
            listed = True
        if sid in role.on_demand:
            role_on_demand.append(rid)
            listed = True
        if listed:
            role_ids.append(rid)
    direct: list[str] = []
    via_role: list[str] = []
    for key in project_keys(vault):
        proj = vault.projects[key]
        if sid in proj.core or sid in proj.on_demand:
            direct.append(key)
            continue
        for raw_role in proj.roles:
            role = vault.roles.get(raw_role)
            if role is not None and (sid in role.core or sid in role.on_demand):
                via_role.append(key)
                break
    affects_set = set(direct) | set(via_role)
    return {
        "id": sid,
        "title": stanza.title,
        "size": size_fields(stanza.content),
        "roles": {"core": role_core, "on_demand": role_on_demand},
        "direct_projects": direct,
        "via_role_projects": via_role,
        "expected": {"roles": list(role_ids), "projects": list(direct)},
        "affects_projects": [key for key in project_keys(vault) if key in affects_set],
    }


def delete_stanza(
    vault_or_root: Path | str,
    stanza_id: str,
    *,
    why: str,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    try:
        sid = validate_stanza_id(stanza_id)
    except InvalidIdentity as exc:
        return _identity_error(stanza_id, exc)
    reason = _clean_why(why)
    if reason is None:
        return {"ok": False, "error": "missing_why"}
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    if sid not in vault.stanzas:
        return {"ok": False, "error": "not_found", "id": sid}
    plan = _stanza_delete_plan(vault, sid)
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated
    paths: list[Path] = []
    for rid in plan["expected"]["roles"]:
        role = vault.roles[rid]
        data = dict(role.raw)
        data["core"] = [item for item in role.core if item != sid]
        data["on_demand"] = [item for item in role.on_demand if item != sid]
        paths.append(_write_role_file(vault_root, rid, data))
    for key in plan["expected"]["projects"]:
        proj = vault.projects[key]
        core = [item for item in proj.core if item != sid]
        on_demand = [item for item in proj.on_demand if item != sid]
        paths.append(_write_map(proj.path, proj.raw, core, on_demand))
    md, prov = _stanza_paths(vault_root, sid)
    md.unlink(missing_ok=True)
    paths.append(md)
    if prov.is_file():
        prov.unlink()
        paths.append(prov)
    legacy = _legacy_why_log_path(vault_root, sid)
    if legacy.is_file():
        legacy.unlink()
        paths.append(legacy)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"delete stanza {sid}", reason),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {**plan, "ok": True, "written": True}
    result.update(reviewed)
    return result


def _role_delete_plan(vault, rid: str) -> dict:
    role = vault.roles[rid]
    members: list[str] = []
    seen: set[str] = set()
    for sid in list(role.core) + list(role.on_demand):
        if sid in seen:
            continue
        seen.add(sid)
        members.append(sid)
    member_rows: list[dict] = []
    for sid in members:
        stanza = vault.stanzas.get(sid)
        row: dict[str, Any] = {"id": sid}
        if stanza is not None:
            row["title"] = stanza.title
            row.update(size_fields(stanza.content))
        member_rows.append(row)
    projects = [key for key in project_keys(vault) if rid in vault.projects[key].roles]
    return {
        "id": rid,
        "name": role.name,
        "members": member_rows,
        "projects": projects,
        "expected": {"projects": list(projects), "stanzas": list(members)},
        "affects_projects": list(projects),
    }


def delete_role(
    vault_or_root: Path | str,
    role_id: str,
    *,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    try:
        rid = validate_role_id(role_id)
    except InvalidIdentity as exc:
        return _identity_error(role_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    if rid not in vault.roles:
        return {"ok": False, "error": "not_found", "id": rid}
    plan = _role_delete_plan(vault, rid)
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated
    paths: list[Path] = []
    for key in plan["expected"]["projects"]:
        proj = vault.projects[key]
        roles = [item for item in proj.roles if item != rid]
        paths.append(_write_map(proj.path, proj.raw, roles=roles))
    for sid in plan["expected"]["stanzas"]:
        stanza = vault.stanzas.get(sid)
        if stanza is None:
            continue
        _remove_frontmatter_role(stanza.path, rid)
        paths.append(stanza.path)
    role_path = vault.roles[rid].path
    role_path.unlink(missing_ok=True)
    paths.append(role_path)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"delete role {rid}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {**plan, "ok": True, "written": True}
    result.update(reviewed)
    return result


def delete_project(
    vault_or_root: Path | str,
    project: str,
    *,
    confirm: bool = False,
    expected: dict | None = None,
    why: str | None = None,
) -> dict:
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    if key == GLOBAL_PROJECT:
        return {"ok": False, "error": "cannot_delete_global"}
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "not_found", "id": key}
    summary = get_project(vault, key)
    plan = {
        "project": key,
        "name": proj.name,
        "repo": proj.repo,
        "aka": list(proj.aka),
        "roles": list(proj.roles),
        "core": list(proj.core),
        "on_demand": list(proj.on_demand),
        "notes": proj.notes is not None,
        "size": summary.get("size") if summary.get("ok") else None,
        "statement": f"Only projects/{key}/ goes away. Stanzas and roles stay.",
        "expected": {"projects": [key]},
        "affects_projects": [key],
    }
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated
    folder = proj.path
    shutil.rmtree(folder)
    reviewed = apply_review(
        vault_root,
        [folder],
        _review_message(f"delete project {key}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {**plan, "ok": True, "written": True}
    result.update(reviewed)
    return result


def create_role(
    vault_or_root: Path | str,
    role_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    why: str | None = None,
) -> dict:
    try:
        rid = validate_role_id(role_id)
    except InvalidIdentity as exc:
        return _identity_error(role_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    if rid in vault.roles:
        return {"ok": False, "error": "already_exists", "id": rid}
    core_ids = _as_list(core)
    on_demand_ids = _as_list(on_demand)
    for sid in core_ids + on_demand_ids:
        try:
            validated = validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)
        if validated not in vault.stanzas:
            return {"ok": False, "error": "missing_stanza", "id": validated}
    data: dict[str, Any] = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    data["core"] = core_ids
    data["on_demand"] = on_demand_ids
    path = _write_role_file(vault_root, rid, data)
    paths = [path]
    for sid in core_ids + on_demand_ids:
        stanza = vault.stanzas[sid]
        _add_frontmatter_role(stanza.path, rid)
        paths.append(stanza.path)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"create role {rid}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "id": rid,
        "name": name,
        "description": description,
        "core": core_ids,
        "on_demand": on_demand_ids,
        "affects_projects": [],
        "written": True,
    }
    result.update(reviewed)
    return result


def _role_membership_plan(
    vault,
    rid: str,
    *,
    add_core: list[str],
    remove_core: list[str],
    add_on_demand: list[str],
    remove_on_demand: list[str],
) -> dict:
    touched = list(
        dict.fromkeys(add_core + remove_core + add_on_demand + remove_on_demand)
    )
    projects = [key for key in project_keys(vault) if rid in vault.projects[key].roles]
    project_rows = []
    for key in projects:
        stanzas = [
            {
                "id": sid,
                "already_in_protocol": stanza_already_in_protocol(
                    vault, key, sid, exclude_role=rid
                ),
            }
            for sid in touched
        ]
        project_rows.append({"project": key, "stanzas": stanzas})
    return {
        "role_id": rid,
        "projects": project_rows,
        "statement": (
            "Maps do not change. Next resolve/materialize for those projects "
            "gains or loses the stanza unless first-wins already hid it."
        ),
        "expected": {
            "add_core": list(add_core),
            "remove_core": list(remove_core),
            "add_on_demand": list(add_on_demand),
            "remove_on_demand": list(remove_on_demand),
            "projects": list(projects),
        },
        "affects_projects": list(projects),
    }


def update_role(
    vault_or_root: Path | str,
    role_id: str,
    *,
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
    try:
        rid = validate_role_id(role_id)
    except InvalidIdentity as exc:
        return _identity_error(role_id, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    role = vault.roles.get(rid)
    if role is None:
        return {"ok": False, "error": "not_found", "id": rid}
    membership = any(
        value is not None
        for value in (add_core, remove_core, add_on_demand, remove_on_demand)
    )
    if not membership:
        if name is None and description is None:
            return {"ok": False, "error": "no_changes", "id": rid}
        data = dict(role.raw)
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if "core" not in data:
            data["core"] = list(role.core)
        if "on_demand" not in data:
            data["on_demand"] = list(role.on_demand)
        path = _write_role_file(vault_root, rid, data)
        reviewed = apply_review(
            vault_root,
            [path],
            _review_message(f"update role {rid}", _clean_why(why)),
            policy=policy,
        )
        if not reviewed["ok"]:
            return reviewed
        result = {
            "ok": True,
            "id": rid,
            "written": True,
            "affects_projects": [],
        }
        result.update(reviewed)
        return result

    add_core_ids = _as_list(add_core)
    remove_core_ids = _as_list(remove_core)
    add_on_demand_ids = _as_list(add_on_demand)
    remove_on_demand_ids = _as_list(remove_on_demand)
    for sid in add_core_ids + add_on_demand_ids:
        try:
            validated = validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)
        if validated not in vault.stanzas:
            return {"ok": False, "error": "missing_stanza", "id": validated}
    for sid in remove_core_ids + remove_on_demand_ids:
        try:
            validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)

    plan = _role_membership_plan(
        vault,
        rid,
        add_core=add_core_ids,
        remove_core=remove_core_ids,
        add_on_demand=add_on_demand_ids,
        remove_on_demand=remove_on_demand_ids,
    )
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated

    core = list(role.core)
    on_demand = list(role.on_demand)
    for sid in add_core_ids:
        if sid not in core:
            core.append(sid)
    core = [item for item in core if item not in set(remove_core_ids)]
    for sid in add_on_demand_ids:
        if sid not in on_demand:
            on_demand.append(sid)
    on_demand = [item for item in on_demand if item not in set(remove_on_demand_ids)]
    original_members = set(role.core) | set(role.on_demand)
    final_members = set(core) | set(on_demand)
    data = dict(role.raw)
    data["core"] = core
    data["on_demand"] = on_demand
    data.pop("available", None)
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    paths = [_write_role_file(vault_root, rid, data)]
    for sid in sorted(final_members - original_members):
        _add_frontmatter_role(vault.stanzas[sid].path, rid)
        paths.append(vault.stanzas[sid].path)
    for sid in sorted(original_members - final_members):
        stanza = vault.stanzas.get(sid)
        if stanza is None:
            continue
        _remove_frontmatter_role(stanza.path, rid)
        paths.append(stanza.path)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"update role {rid}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {**plan, "ok": True, "written": True}
    result.update(reviewed)
    return result


def create_project(
    vault_or_root: Path | str,
    project: str,
    *,
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
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    if key in vault.projects:
        return {"ok": False, "error": "already_exists", "id": key}
    role_ids = _as_list(roles)
    core_ids = _as_list(core)
    on_demand_ids = _as_list(on_demand)
    skill_ids = _as_list(skills)
    for rid in role_ids:
        try:
            validated = validate_role_id(rid)
        except InvalidIdentity as exc:
            return _identity_error(rid, exc)
        if validated not in vault.roles:
            return {"ok": False, "error": "missing_role", "id": validated}
    for sid in core_ids + on_demand_ids:
        try:
            validated = validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)
        if validated not in vault.stanzas:
            return {"ok": False, "error": "missing_stanza", "id": validated}
    for skill_id in skill_ids:
        try:
            validated = validate_skill_id(skill_id)
        except InvalidIdentity as exc:
            return _identity_error(skill_id, exc)
        if validated not in vault.skills:
            return {"ok": False, "error": "missing_skill", "id": validated}
    data: dict[str, Any] = {}
    if repo is not None:
        data["repo"] = repo
    if name is not None:
        data["name"] = name
    if aka is not None:
        data["aka"] = list(aka)
    if role_ids:
        data["roles"] = role_ids
    data["core"] = core_ids
    data["on_demand"] = on_demand_ids
    if skill_ids:
        data["skills"] = skill_ids
    if include_global is not None:
        data["include_global"] = include_global
    folder = vault_root / "projects" / key
    folder.mkdir(parents=True, exist_ok=True)
    map_path = folder / "map.yaml"
    map_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    paths = [map_path]
    if notes is not None:
        notes_path = folder / "notes.md"
        notes_path.write_text(notes, encoding="utf-8")
        paths.append(notes_path)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"create project {key}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed
    result = {
        "ok": True,
        "project": key,
        "roles": role_ids,
        "core": core_ids,
        "on_demand": on_demand_ids,
        "skills": skill_ids,
        "affects_projects": [key],
        "written": True,
    }
    result.update(reviewed)
    return result


def update_project(
    vault_or_root: Path | str,
    project: str,
    *,
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
    try:
        key = validate_project_key(project)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    vault_root = Path(vault_or_root)
    policy = load_review_policy(vault_root)
    if not policy["ok"]:
        return policy
    vault = load_vault(vault_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "not_found", "id": key}

    add_role_ids = _as_list(add_roles)
    remove_role_ids = _as_list(remove_roles)
    add_core_ids = _as_list(add_core)
    remove_core_ids = _as_list(remove_core)
    add_on_demand_ids = _as_list(add_on_demand)
    remove_on_demand_ids = _as_list(remove_on_demand)
    add_skill_ids = _as_list(add_skills)
    remove_skill_ids = _as_list(remove_skills)

    for rid in add_role_ids:
        try:
            validated = validate_role_id(rid)
        except InvalidIdentity as exc:
            return _identity_error(rid, exc)
        if validated not in vault.roles:
            return {"ok": False, "error": "missing_role", "id": validated}
    for rid in remove_role_ids:
        try:
            validate_role_id(rid)
        except InvalidIdentity as exc:
            return _identity_error(rid, exc)
    for sid in add_core_ids + add_on_demand_ids:
        try:
            validated = validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)
        if validated not in vault.stanzas:
            return {"ok": False, "error": "missing_stanza", "id": validated}
        if validated in proj.core:
            return {
                "ok": False,
                "error": "already_linked",
                "id": validated,
                "target": "core",
                "project": key,
            }
        if validated in proj.on_demand:
            return {
                "ok": False,
                "error": "already_linked",
                "id": validated,
                "target": "on_demand",
                "project": key,
            }
    for sid in remove_core_ids + remove_on_demand_ids:
        try:
            validate_stanza_id(sid)
        except InvalidIdentity as exc:
            return _identity_error(sid, exc)
    for skill_id in add_skill_ids:
        try:
            validated = validate_skill_id(skill_id)
        except InvalidIdentity as exc:
            return _identity_error(skill_id, exc)
        if validated not in vault.skills:
            return {"ok": False, "error": "missing_skill", "id": validated}
        if validated in proj.skills:
            return {
                "ok": False,
                "error": "already_linked",
                "id": validated,
                "project": key,
            }
    for skill_id in remove_skill_ids:
        try:
            validate_skill_id(skill_id)
        except InvalidIdentity as exc:
            return _identity_error(skill_id, exc)

    roles = list(proj.roles)
    for rid in add_role_ids:
        if rid not in roles:
            roles.append(rid)
    roles = [item for item in roles if item not in set(remove_role_ids)]
    core = list(proj.core)
    for sid in add_core_ids:
        if sid not in core:
            core.append(sid)
    core = [item for item in core if item not in set(remove_core_ids)]
    on_demand = list(proj.on_demand)
    for sid in add_on_demand_ids:
        if sid not in on_demand:
            on_demand.append(sid)
    on_demand = [item for item in on_demand if item not in set(remove_on_demand_ids)]
    skills = list(proj.skills)
    for skill_id in add_skill_ids:
        if skill_id not in skills:
            skills.append(skill_id)
    skills = [item for item in skills if item not in set(remove_skill_ids)]

    fields = (
        repo,
        name,
        aka,
        include_global,
        notes,
        add_roles,
        remove_roles,
        add_core,
        remove_core,
        add_on_demand,
        remove_on_demand,
        add_skills,
        remove_skills,
    )
    if all(value is None for value in fields):
        return {"ok": False, "error": "no_changes", "id": key}

    path = _write_map(
        proj.path,
        proj.raw,
        core,
        on_demand,
        roles=roles,
        skills=skills,
        repo=repo,
        name=name,
        aka=aka,
        include_global=include_global,
        set_repo=repo is not None,
        set_name=name is not None,
        set_aka=aka is not None,
        set_include_global=include_global is not None,
    )
    paths = [path]
    if notes is not None:
        notes_path = proj.path / "notes.md"
        notes_path.write_text(notes, encoding="utf-8")
        paths.append(notes_path)
    reviewed = apply_review(
        vault_root,
        paths,
        _review_message(f"update project {key}", _clean_why(why)),
        policy=policy,
    )
    if not reviewed["ok"]:
        return reviewed

    members: list[dict] = []
    seen_members: set[str] = set()
    for rid in add_role_ids + remove_role_ids:
        role = vault.roles.get(rid)
        if role is None:
            continue
        for sid in list(role.core) + list(role.on_demand):
            if sid in seen_members:
                continue
            seen_members.add(sid)
            stanza = vault.stanzas.get(sid)
            row: dict[str, Any] = {"id": sid}
            if stanza is not None:
                row["title"] = stanza.title
                row["description"] = stanza.description
                row.update(size_fields(stanza.content))
            members.append(row)

    summary = get_project(vault_root, key)
    result = {
        "ok": True,
        "written": True,
        "project": key,
        "roles": roles,
        "core": core,
        "on_demand": on_demand,
        "skills": skills,
        "members": members,
        "size": summary.get("size") if summary.get("ok") else None,
        "affects_projects": affects_for_map_edit(vault, key),
    }
    result.update(reviewed)
    return result
