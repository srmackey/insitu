"""Blast radius and protocol-membership helpers for 0.6 writes."""

from __future__ import annotations

from typing import Any

from insitu.identity import GLOBAL_PROJECT
from insitu.models import Vault
from insitu.resolve import (
    composed_global_core,
    expand_import_field,
    expand_role_field,
    first_wins,
)


def project_keys(vault: Vault) -> list[str]:
    keys: list[str] = []
    if GLOBAL_PROJECT in vault.projects:
        keys.append(GLOBAL_PROJECT)
    keys.extend(sorted(k for k in vault.projects if k != GLOBAL_PROJECT))
    return keys


def projects_including_global(vault: Vault) -> list[str]:
    keys: list[str] = []
    if GLOBAL_PROJECT in vault.projects:
        keys.append(GLOBAL_PROJECT)
    keys.extend(
        sorted(
            key
            for key, proj in vault.projects.items()
            if key != GLOBAL_PROJECT and proj.include_global
        )
    )
    return keys


def composed_id_sets(vault: Vault, project: str) -> tuple[set[str], set[str]]:
    proj = vault.projects[project]
    include_global = False if project == GLOBAL_PROJECT else proj.include_global
    global_core: list[str] = []
    if include_global:
        composed = composed_global_core(vault)
        if not isinstance(composed, dict):
            global_core = composed
    role_core = expand_role_field(vault, proj.roles, "core")
    if isinstance(role_core, dict):
        role_core = []
    role_on_demand = expand_role_field(vault, proj.roles, "on_demand")
    if isinstance(role_on_demand, dict):
        role_on_demand = []
    import_core = expand_import_field(vault, proj.imports, "core")
    import_core_ids = (
        [sid for sid, _pack in import_core] if not isinstance(import_core, dict) else []
    )
    import_on_demand = expand_import_field(vault, proj.imports, "on_demand")
    import_on_demand_ids = (
        [sid for sid, _pack in import_on_demand]
        if not isinstance(import_on_demand, dict)
        else []
    )
    core = set(first_wins(global_core, role_core, import_core_ids, list(proj.core)))
    on_demand = set(first_wins(role_on_demand, import_on_demand_ids, list(proj.on_demand)))
    return core, on_demand


def projects_composed_including(vault: Vault, article_id: str) -> list[str]:
    found: list[str] = []
    for key in project_keys(vault):
        core, on_demand = composed_id_sets(vault, key)
        if article_id in core or article_id in on_demand:
            found.append(key)
    return found


def projects_carrying_role(vault: Vault, role_id: str) -> list[str]:
    """Maps whose subscription lists this role.

    A role is a bundle, so editing its membership changes what every one of
    these maps composes without touching any of them.
    """
    return [
        key
        for key in project_keys(vault)
        if role_id in list(vault.projects[key].roles or [])
    ]


def projects_listing_skill(vault: Vault, skill_id: str) -> list[str]:
    """Maps whose subscription lists this skill."""
    return [
        key
        for key in project_keys(vault)
        if skill_id in list(vault.projects[key].skills or [])
    ]


def article_already_in_protocol(
    vault: Vault,
    project: str,
    article_id: str,
    *,
    exclude_role: str | None = None,
) -> bool:
    proj = vault.projects[project]
    include_global = False if project == GLOBAL_PROJECT else proj.include_global
    if include_global:
        composed = composed_global_core(vault)
        if not isinstance(composed, dict) and article_id in composed:
            return True
    for raw_role in proj.roles:
        if exclude_role is not None and raw_role == exclude_role:
            continue
        role = vault.roles.get(raw_role)
        if role is None:
            continue
        if article_id in role.core or article_id in role.on_demand:
            return True
    return article_id in proj.core or article_id in proj.on_demand


def affects_for_map_edit(vault: Vault, project: str) -> list[str]:
    if project == GLOBAL_PROJECT:
        return projects_including_global(vault)
    return [project]


def normalize_expected(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, list):
            out[key] = sorted(str(entry) for entry in item)
        else:
            out[key] = item
    return out


def expected_matches(plan: Any, given: Any) -> bool:
    if not isinstance(plan, dict) or not isinstance(given, dict):
        return False
    return normalize_expected(plan) == normalize_expected(given)
