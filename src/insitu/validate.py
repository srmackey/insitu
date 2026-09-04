"""Vault health check. Read-only unless fix=true (map dupes, legacy keys)."""

from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml

from insitu.affects import composed_id_sets, project_keys
from insitu.identity import (
    GLOBAL_PROJECT,
    InvalidIdentity,
    validate_role_id,
    validate_skill_id,
    validate_article_id,
)
from insitu.library import cited_versions
from insitu.models import Role, Vault
from insitu.resolve import (
    composed_global_core,
    expand_import_groups,
    expand_role_field,
    expand_role_groups,
    first_wins,
)
from insitu.store import (
    both_keys_present,
    files_written,
    load_on_demand_list,
    load_vault,
    read_frontmatter,
    read_yaml,
)


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def _dedupe(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _check_id_list(
    issues: list[dict],
    raw_ids: list[str],
    *,
    vault: Vault,
    list_name: str,
    project: str | None = None,
    role: str | None = None,
) -> None:
    seen: set[str] = set()
    for raw_id in raw_ids:
        try:
            sid = validate_article_id(raw_id)
        except InvalidIdentity:
            issue: dict = {
                "kind": "invalid_identity",
                "id": raw_id,
                "list": list_name,
            }
            if project is not None:
                issue["project"] = project
            if role is not None:
                issue["role"] = role
            issues.append(issue)
            continue
        if sid not in vault.articles:
            issue = {
                "kind": "missing_article",
                "id": sid,
                "list": list_name,
            }
            if project is not None:
                issue["project"] = project
            if role is not None:
                issue["role"] = role
            issues.append(issue)
        if sid in seen:
            issue = {
                "kind": "duplicate",
                "id": sid,
                "list": list_name,
            }
            if project is not None:
                issue["project"] = project
            if role is not None:
                issue["role"] = role
            issues.append(issue)
        seen.add(sid)


def _role_member_ids(role: Role) -> list[str]:
    members: list[str] = []
    seen: set[str] = set()
    for raw_id in list(role.core) + list(role.on_demand):
        try:
            sid = validate_article_id(raw_id)
        except InvalidIdentity:
            continue
        if sid in seen:
            continue
        seen.add(sid)
        members.append(sid)
    return members


def _cross_source_duplicates(
    issues: list[dict],
    project: str,
    list_name: str,
    sources: list[list[str]],
) -> None:
    seen: set[str] = set()
    for source in sources:
        for sid in source:
            if sid in seen:
                issues.append(
                    {
                        "kind": "duplicate",
                        "project": project,
                        "id": sid,
                        "list": list_name,
                    }
                )
            seen.add(sid)


def _collect_issues(vault: Vault) -> list[dict]:
    issues: list[dict] = []
    for sid, article in sorted(vault.articles.items()):
        if article.frontmatter_id is not None and article.frontmatter_id != sid:
            issues.append(
                {
                    "kind": "id_mismatch",
                    "path": sid,
                    "id": article.frontmatter_id,
                }
            )
        missing_fields = []
        if not article.title:
            missing_fields.append("title")
        if not article.description:
            missing_fields.append("description")
        if missing_fields:
            issues.append(
                {
                    "kind": "missing_frontmatter",
                    "id": sid,
                    "fields": missing_fields,
                }
            )
        for declared in article.conflicts:
            # A conflict naming an article that does not exist refuses nothing.
            # It reads like a live guard and is inert, which is worse than an
            # absent one, so it is an issue rather than a hygiene finding.
            if str(declared) not in vault.articles:
                issues.append(
                    {
                        "kind": "missing_conflict",
                        "id": sid,
                        "conflicts": str(declared),
                    }
                )
    for rid, role in sorted(vault.roles.items()):
        for list_name in ("core", "on_demand"):
            _check_id_list(
                issues,
                getattr(role, list_name),
                vault=vault,
                list_name=list_name,
                role=rid,
            )

    for key, proj in sorted(vault.projects.items(), key=lambda kv: (kv[0] != GLOBAL_PROJECT, kv[0])):
        for list_name in ("core", "on_demand"):
            _check_id_list(
                issues,
                getattr(proj, list_name),
                vault=vault,
                list_name=list_name,
                project=key,
            )

        for raw_role in proj.roles:
            try:
                role_id = validate_role_id(raw_role)
            except InvalidIdentity:
                issues.append(
                    {
                        "kind": "invalid_identity",
                        "project": key,
                        "id": raw_role,
                        "list": "roles",
                    }
                )
                continue
            if role_id not in vault.roles:
                issues.append(
                    {
                        "kind": "missing_role",
                        "project": key,
                        "id": role_id,
                    }
                )

        core_sources: list[list[str]] = []
        if key != GLOBAL_PROJECT and proj.include_global:
            composed = composed_global_core(vault)
            if not isinstance(composed, dict):
                core_sources.append(composed)
        role_core_groups = expand_role_groups(vault, proj.roles, "core")
        if not isinstance(role_core_groups, dict):
            core_sources.extend(first_wins(group) for group in role_core_groups)
        core_sources.append(first_wins(list(proj.core)))
        _cross_source_duplicates(issues, key, "core", core_sources)

        avail_sources: list[list[str]] = []
        role_on_demand_groups = expand_role_groups(vault, proj.roles, "on_demand")
        if not isinstance(role_on_demand_groups, dict):
            avail_sources.extend(first_wins(group) for group in role_on_demand_groups)
        avail_sources.append(first_wins(list(proj.on_demand)))
        _cross_source_duplicates(issues, key, "on_demand", avail_sources)

        _collect_import_issues(issues, vault, key)
        _collect_skill_map_issues(issues, vault, key)

    _collect_pack_tree_issues(issues, vault)
    _collect_skill_catalog_issues(issues, vault)
    _collect_role_skills_issues(issues, vault)

    for key, proj in sorted(vault.projects.items(), key=lambda kv: (kv[0] != GLOBAL_PROJECT, kv[0])):
        if both_keys_present(proj.raw):
            issues.append({"kind": "both_keys_present", "project": key})
    for rid, role in sorted(vault.roles.items()):
        if both_keys_present(role.raw):
            issues.append({"kind": "both_keys_present", "role": rid})
    return issues


def _collect_findings(vault: Vault) -> dict:
    empty_projects: list[dict] = []
    for key in project_keys(vault):
        proj = vault.projects[key]
        if not proj.roles and not proj.core and not proj.on_demand and not proj.imports:
            empty_projects.append({"id": key, "label": proj.name or key})

    empty_roles: list[dict] = []
    for rid, role in sorted(vault.roles.items()):
        if not role.core and not role.on_demand:
            empty_roles.append({"id": rid, "label": role.name or rid})

    referenced: set[str] = set()
    for proj in vault.projects.values():
        referenced.update(proj.core)
        referenced.update(proj.on_demand)
    for role in vault.roles.values():
        referenced.update(role.core)
        referenced.update(role.on_demand)

    unreferenced: list[dict] = []
    for sid, article in sorted(vault.articles.items()):
        if sid not in referenced:
            unreferenced.append({"id": sid, "label": article.title or sid})
    unreferenced_ids = {item["id"] for item in unreferenced}

    in_protocol: set[str] = set()
    if GLOBAL_PROJECT in vault.projects:
        composed = composed_global_core(vault)
        if not isinstance(composed, dict):
            in_protocol.update(composed)
    for key in project_keys(vault):
        if key == GLOBAL_PROJECT:
            continue
        core, on_demand = composed_id_sets(vault, key)
        in_protocol.update(core)
        in_protocol.update(on_demand)

    not_in: list[dict] = []
    for sid, article in sorted(vault.articles.items()):
        if sid in unreferenced_ids:
            continue
        if sid not in in_protocol:
            not_in.append({"id": sid, "label": article.title or sid})

    unreferenced_version: list[dict] = []
    cited = cited_versions(vault)
    for pack_id, versions in sorted(vault.library.items()):
        for version in sorted(versions):
            if (pack_id, version) not in cited:
                unreferenced_version.append({"pack": pack_id, "version": version})

    referenced_skills: set[str] = set()
    for proj in vault.projects.values():
        referenced_skills.update(proj.skills)
    unreferenced_skill: list[dict] = []
    for sid, skill in sorted(vault.skills.items()):
        if sid not in referenced_skills:
            unreferenced_skill.append({"id": sid, "label": skill.name or sid})

    global_skills_not_inherited: list[dict] = []
    if GLOBAL_PROJECT in vault.projects and vault.projects[GLOBAL_PROJECT].skills:
        global_skills_not_inherited.append(
            {
                "project": GLOBAL_PROJECT,
                "skills": list(vault.projects[GLOBAL_PROJECT].skills),
            }
        )

    return {
        "empty_projects": empty_projects,
        "empty_roles": empty_roles,
        "unreferenced": unreferenced,
        "unreferenced_version": unreferenced_version,
        "unreferenced_skill": unreferenced_skill,
        "not_in_any_protocol": not_in,
        "legacy_available_key": _legacy_available_findings(vault),
        "global_skills_not_inherited": global_skills_not_inherited,
        "skill_missing_skill_md": _skill_missing_skill_md(vault),
    }


def _collect_skill_map_issues(issues: list[dict], vault: Vault, project: str) -> None:
    proj = vault.projects[project]
    seen: set[str] = set()
    for raw_id in proj.skills:
        try:
            sid = validate_skill_id(raw_id)
        except InvalidIdentity:
            issues.append(
                {
                    "kind": "invalid_identity",
                    "id": raw_id,
                    "list": "skills",
                    "project": project,
                }
            )
            continue
        if sid not in vault.skills:
            issues.append(
                {
                    "kind": "missing_skill",
                    "id": sid,
                    "list": "skills",
                    "project": project,
                }
            )
        if sid in seen:
            issues.append(
                {
                    "kind": "duplicate",
                    "id": sid,
                    "list": "skills",
                    "project": project,
                }
            )
        seen.add(sid)


def _collect_skill_catalog_issues(issues: list[dict], vault: Vault) -> None:
    for sid, skill in sorted(vault.skills.items()):
        if skill.name and skill.name != sid:
            issues.append(
                {
                    "kind": "skill_name_mismatch",
                    "id": sid,
                    "name": skill.name,
                }
            )
        if not skill.description:
            issues.append(
                {
                    "kind": "skill_missing_description",
                    "id": sid,
                }
            )
    skills_root = vault.root / "skills"
    if not skills_root.is_dir():
        return
    for child in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        try:
            validate_skill_id(child.name)
        except InvalidIdentity:
            issues.append(
                {
                    "kind": "invalid_skill_path",
                    "id": child.name,
                    "path": str(child),
                }
            )
        for nested in child.rglob("SKILL.md"):
            rel = nested.relative_to(skills_root)
            if len(rel.parts) > 2:
                issues.append(
                    {
                        "kind": "invalid_skill_path",
                        "id": rel.as_posix(),
                        "path": str(nested.parent),
                    }
                )


def _collect_role_skills_issues(issues: list[dict], vault: Vault) -> None:
    for rid, role in sorted(vault.roles.items()):
        if "skills" in role.raw:
            issues.append(
                {
                    "kind": "role_skills_not_supported",
                    "role": rid,
                }
            )


def _skill_missing_skill_md(vault: Vault) -> list[dict]:
    found: list[dict] = []
    skills_root = vault.root / "skills"
    if not skills_root.is_dir():
        return found
    for child in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        try:
            sid = validate_skill_id(child.name)
        except InvalidIdentity:
            continue
        if not (child / "SKILL.md").is_file():
            found.append({"id": sid, "path": str(child)})
    return found


def _collect_import_issues(issues: list[dict], vault: Vault, project: str) -> None:
    proj = vault.projects[project]
    groups = expand_import_groups(vault, proj.imports, "core")
    if isinstance(groups, dict) and groups.get("error") == "duplicate_import_article":
        issues.append(
            {
                "kind": "duplicate_import_article",
                "project": project,
                "id": groups.get("id"),
                "pack": groups.get("pack"),
                "version": groups.get("version"),
            }
        )
    for record in proj.imports:
        if record.version == "latest":
            if not vault.library.get(record.pack):
                issues.append(
                    {
                        "kind": "broken_pin",
                        "project": project,
                        "pack": record.pack,
                        "version": "latest",
                    }
                )
            continue
        pack = vault.library.get(record.pack, {}).get(record.version)
        if pack is None:
            issues.append(
                {
                    "kind": "broken_pin",
                    "project": project,
                    "pack": record.pack,
                    "version": record.version,
                }
            )
            continue
        if record.article_members():
            for sid in record.article_members():
                if sid not in pack.articles:
                    issues.append(
                        {
                            "kind": "missing_article",
                            "project": project,
                            "id": sid,
                            "pack": record.pack,
                            "version": record.version,
                            "list": "imports",
                        }
                    )


def _collect_pack_tree_issues(issues: list[dict], vault: Vault) -> None:
    for pack_id, versions in sorted(vault.library.items()):
        for version, pack in sorted(versions.items()):
            listed = [str(item) for item in (pack.pack_yaml.get("articles") or [])]
            if pack.role is not None:
                listed.extend(pack.role.core)
                listed.extend(pack.role.on_demand)
            seen: set[str] = set()
            for sid in listed:
                if sid in seen:
                    continue
                seen.add(sid)
                if sid not in pack.articles:
                    issues.append(
                        {
                            "kind": "missing_article",
                            "id": sid,
                            "pack": pack_id,
                            "version": version,
                            "list": "pack",
                        }
                    )
            for sid, article in sorted(pack.articles.items()):
                if article.frontmatter_id is not None and article.frontmatter_id != sid:
                    issues.append(
                        {
                            "kind": "id_mismatch",
                            "path": sid,
                            "id": article.frontmatter_id,
                            "pack": pack_id,
                            "version": version,
                        }
                    )


def _legacy_available_findings(vault: Vault) -> list[dict]:
    found: list[dict] = []
    for key, proj in sorted(vault.projects.items(), key=lambda kv: (kv[0] != GLOBAL_PROJECT, kv[0])):
        raw = proj.raw
        if "available" in raw and "on_demand" not in raw:
            found.append({"project": key, "path": str(proj.path / "map.yaml")})
    for rid, role in sorted(vault.roles.items()):
        raw = role.raw
        if "available" in raw and "on_demand" not in raw:
            found.append({"role": rid, "path": str(role.path)})
    return found


def _apply_duplicate_fixes(vault: Vault) -> list[dict]:
    fixed: list[dict] = []
    keys: list[str] = []
    if GLOBAL_PROJECT in vault.projects:
        keys.append(GLOBAL_PROJECT)
    keys.extend(sorted(k for k in vault.projects if k != GLOBAL_PROJECT))

    global_role_core: list[str] = []
    if GLOBAL_PROJECT in vault.projects:
        expanded = expand_role_field(vault, vault.projects[GLOBAL_PROJECT].roles, "core")
        if not isinstance(expanded, dict):
            global_role_core = expanded

    global_core: list[str] = []
    for key in keys:
        proj = vault.projects[key]
        map_path = proj.path / "map.yaml"
        data = read_yaml(map_path)
        if not isinstance(data, dict):
            data = {}
        core = list(data.get("core") or [])
        on_demand = load_on_demand_list(data)
        new_core = _dedupe(core)
        new_on_demand = _dedupe(on_demand)
        skills = list(data.get("skills") or [])
        new_skills = _dedupe(skills)
        include_global = data.get("include_global", True)
        if include_global is None:
            include_global = True
        blocked: set[str] = set()
        if key == GLOBAL_PROJECT:
            blocked.update(global_role_core)
        else:
            if include_global:
                blocked.update(first_wins(global_role_core, global_core))
            role_core = expand_role_field(vault, proj.roles, "core")
            if not isinstance(role_core, dict):
                blocked.update(role_core)
        new_core = [item for item in new_core if item not in blocked]
        role_on_demand = expand_role_field(vault, proj.roles, "on_demand")
        if not isinstance(role_on_demand, dict):
            blocked_avail = set(role_on_demand)
            new_on_demand = [item for item in new_on_demand if item not in blocked_avail]
        if new_core == core and new_on_demand == on_demand and new_skills == skills:
            if key == GLOBAL_PROJECT:
                global_core = new_core
            continue
        dropped_core = [item for item in core if item not in new_core]
        dropped_on_demand = [item for item in on_demand if item not in new_on_demand]
        dropped_skills = [item for item in skills if item not in new_skills]
        for item in dropped_core:
            fixed.append(
                {"kind": "duplicate", "project": key, "id": item, "list": "core"}
            )
        for item in dropped_on_demand:
            fixed.append(
                {"kind": "duplicate", "project": key, "id": item, "list": "on_demand"}
            )
        for item in dropped_skills:
            fixed.append(
                {"kind": "duplicate", "project": key, "id": item, "list": "skills"}
            )
        data["core"] = new_core
        data["on_demand"] = new_on_demand
        data.pop("available", None)
        if new_skills:
            data["skills"] = new_skills
        else:
            data.pop("skills", None)
        map_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        if key == GLOBAL_PROJECT:
            global_core = new_core
    return fixed


def _paths_for_fixes(vault: Vault, applied: list[dict]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for item in applied:
        path: Path | None = None
        if item.get("kind") == "duplicate" and item.get("project"):
            path = vault.root / "projects" / str(item["project"]) / "map.yaml"
        elif item.get("kind") == "legacy_available_key" and item.get("path"):
            path = Path(str(item["path"]))
        if path is None or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _apply_legacy_key_fixes(vault: Vault) -> list[dict]:
    fixed: list[dict] = []
    for item in _legacy_available_findings(vault):
        path = Path(item["path"])
        data = read_yaml(path)
        if not isinstance(data, dict):
            continue
        if "on_demand" in data or "available" not in data:
            continue
        data["on_demand"] = list(data.get("available") or [])
        data.pop("available", None)
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        entry = {"kind": "legacy_available_key", "path": str(path)}
        if "project" in item:
            entry["project"] = item["project"]
        if "role" in item:
            entry["role"] = item["role"]
        fixed.append(entry)
    return fixed


def validate(vault_or_root: Vault | Path | str, fix: bool = False) -> dict:
    vault = _as_vault(vault_or_root)
    issues = _collect_issues(vault)
    applied: list[dict] = []
    extra: dict = {}
    if fix:
        applied.extend(_apply_duplicate_fixes(vault))
        vault = load_vault(vault.root)
        applied.extend(_apply_legacy_key_fixes(vault))
        vault = load_vault(vault.root)
        issues = _collect_issues(vault)
        if applied:
            extra.update(files_written(vault.root, _paths_for_fixes(vault, applied)))
        else:
            extra["files"] = []
    return {
        "ok": not issues,
        "issues": issues,
        "findings": _collect_findings(vault),
        "fixed": applied,
        **extra,
    }
