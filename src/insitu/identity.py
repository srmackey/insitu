"""Project key and article path rules (DESIGN.md §5)."""

from __future__ import annotations

import re
from pathlib import Path

SEGMENT_RE = re.compile(r"^[a-z0-9-]+$")
VERSION_RE = re.compile(r"^(latest|\d+(\.\d+)*)$")
GLOBAL_PROJECT = "_global"


class InvalidIdentity(ValueError):
    """A project key or article id is not allowed."""


def _is_absolute(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    if path.is_absolute():
        return True
    if re.match(r"^[a-zA-Z]:", value):
        return True
    return value.startswith("/") or value.startswith("\\")


def validate_project_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise InvalidIdentity("project key is empty")
    if _is_absolute(key):
        raise InvalidIdentity(f"project key must not be absolute: {key}")
    if key in {".", ".."} or "/" in key or "\\" in key:
        raise InvalidIdentity(f"project key is not a single folder name: {key}")
    if key == GLOBAL_PROJECT:
        return key
    # Folder basenames may be mixed-case (ProjectName). Stored keys stay lowercase.
    normalized = key.lower()
    if not SEGMENT_RE.fullmatch(normalized):
        raise InvalidIdentity(
            f"project key must be a-z, 0-9, hyphen (or reserved _global): {key}"
        )
    return normalized


def validate_role_id(role_id: str) -> str:
    if not isinstance(role_id, str) or not role_id.strip():
        raise InvalidIdentity("role id is empty")
    if _is_absolute(role_id):
        raise InvalidIdentity(f"role id must not be absolute: {role_id}")
    if role_id in {".", ".."} or "/" in role_id or "\\" in role_id:
        raise InvalidIdentity(f"role id is not a single name: {role_id}")
    if not SEGMENT_RE.fullmatch(role_id):
        raise InvalidIdentity(f"role id must be a-z, 0-9, hyphen: {role_id}")
    return role_id


def validate_skill_id(skill_id: str) -> str:
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise InvalidIdentity("skill id is empty")
    if _is_absolute(skill_id):
        raise InvalidIdentity(f"skill id must not be absolute: {skill_id}")
    if skill_id in {".", ".."} or "/" in skill_id or "\\" in skill_id:
        raise InvalidIdentity(f"skill id is not a single name: {skill_id}")
    if not SEGMENT_RE.fullmatch(skill_id):
        raise InvalidIdentity(f"skill id must be a-z, 0-9, hyphen: {skill_id}")
    return skill_id


def validate_pack_id(pack_id: str) -> str:
    if not isinstance(pack_id, str) or not pack_id.strip():
        raise InvalidIdentity("pack id is empty")
    if _is_absolute(pack_id):
        raise InvalidIdentity(f"pack id must not be absolute: {pack_id}")
    if pack_id in {".", ".."} or "/" in pack_id or "\\" in pack_id:
        raise InvalidIdentity(f"pack id is not a single name: {pack_id}")
    if not SEGMENT_RE.fullmatch(pack_id):
        raise InvalidIdentity(f"pack id must be a-z, 0-9, hyphen: {pack_id}")
    return pack_id


def validate_pack_version(version: str) -> str:
    if not isinstance(version, str) or not version.strip():
        raise InvalidIdentity("pack version is empty")
    if _is_absolute(version):
        raise InvalidIdentity(f"pack version must not be absolute: {version}")
    if version in {".", ".."} or "/" in version or "\\" in version:
        raise InvalidIdentity(f"pack version is not a single name: {version}")
    if not VERSION_RE.fullmatch(version):
        raise InvalidIdentity(
            f"pack version must be latest or dotted digits: {version}"
        )
    return version


def version_sort_key(version: str) -> tuple[int, ...]:
    if version == "latest":
        return (0,)
    return tuple(int(part) for part in version.split("."))


def validate_article_id(article_id: str) -> str:
    if not isinstance(article_id, str) or not article_id.strip():
        raise InvalidIdentity("article id is empty")
    if _is_absolute(article_id):
        raise InvalidIdentity(f"article id must not be absolute: {article_id}")
    normalized = article_id.replace("\\", "/")
    if normalized.startswith("/"):
        raise InvalidIdentity(f"article id must not be absolute: {article_id}")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InvalidIdentity(f"article id must not escape articles/: {article_id}")
    for part in parts:
        if not SEGMENT_RE.fullmatch(part):
            raise InvalidIdentity(
                f"article path segments must be a-z, 0-9, hyphen: {article_id}"
            )
    return normalized
