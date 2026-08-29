"""Load stanzas and project maps from a vault on disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
import yaml

from insitu.identity import (
    InvalidIdentity,
    validate_pack_id,
    validate_pack_version,
    validate_project_key,
    validate_role_id,
    validate_skill_id,
    validate_stanza_id,
)
from insitu.models import ImportRecord, PackRepo, PackVersion, Project, Role, Skill, Stanza, Vault


class VaultReadError(ValueError):
    """A file in the vault could not be parsed."""

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"{path}: {detail}")


def _read_error_detail(exc: Exception) -> str:
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None)
    if mark is not None and problem:
        return f"{problem} (line {mark.line + 1}, column {mark.column + 1})"
    return " ".join(str(exc).split())


def read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise VaultReadError(path, _read_error_detail(exc)) from exc


def read_frontmatter(path: Path) -> frontmatter.Post:
    try:
        return frontmatter.loads(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise VaultReadError(path, _read_error_detail(exc)) from exc


def load_vault(root: str | Path) -> Vault:
    vault_root = Path(root).resolve()
    library, lock = _load_library(vault_root)
    return Vault(
        root=vault_root,
        stanzas=_load_stanzas(vault_root),
        projects=_load_projects(vault_root),
        roles=_load_roles(vault_root),
        skills=_load_skills(vault_root),
        pack_repos=load_pack_repos(vault_root),
        library=library,
        lock=lock,
    )


def _normalize_body(content: str) -> str:
    if content.startswith("\n"):
        content = content[1:]
    return content.rstrip("\n")


def load_stanzas_tree(stanzas_root: Path) -> dict[str, Stanza]:
    stanzas: dict[str, Stanza] = {}
    if not stanzas_root.is_dir():
        return stanzas
    for path in sorted(stanzas_root.rglob("*.md")):
        if path.name.endswith(".prov.md"):
            continue
        rel = path.relative_to(stanzas_root).with_suffix("")
        try:
            stanza_id = validate_stanza_id(rel.as_posix())
        except InvalidIdentity:
            continue
        post = read_frontmatter(path)
        meta = dict(post.metadata or {})
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        frontmatter_id = meta.get("id")
        if frontmatter_id is not None:
            frontmatter_id = str(frontmatter_id)
        stanzas[stanza_id] = Stanza(
            id=stanza_id,
            path=path,
            title=str(meta["title"]) if meta.get("title") else "",
            description=str(meta["description"]) if meta.get("description") else "",
            tags=[str(t) for t in tags],
            content=_normalize_body(post.content or ""),
            frontmatter_id=frontmatter_id,
            roles=_as_str_list(meta.get("roles")),
        )
    return stanzas


def _load_stanzas(root: Path) -> dict[str, Stanza]:
    return load_stanzas_tree(root / "stanzas")


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def both_keys_present(raw: dict[str, Any]) -> bool:
    return "on_demand" in raw and "available" in raw


def load_on_demand_list(raw: dict[str, Any]) -> list[str]:
    if "on_demand" in raw:
        return _as_str_list(raw.get("on_demand"))
    if "available" in raw:
        return _as_str_list(raw.get("available"))
    return []


def _load_projects(root: Path) -> dict[str, Project]:
    projects: dict[str, Project] = {}
    projects_root = root / "projects"
    if not projects_root.is_dir():
        return projects
    for folder in sorted(p for p in projects_root.iterdir() if p.is_dir()):
        try:
            key = validate_project_key(folder.name)
        except InvalidIdentity:
            continue
        map_path = folder / "map.yaml"
        if not map_path.is_file():
            continue
        raw = read_yaml(map_path)
        if not isinstance(raw, dict):
            raw = {}
        notes_path = folder / "notes.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else None
        include = raw.get("include_global", True)
        if include is None:
            include = True
        projects[key] = Project(
            key=key,
            path=folder,
            repo=str(raw["repo"]) if raw.get("repo") else None,
            name=str(raw["name"]) if raw.get("name") else None,
            aka=_as_str_list(raw.get("aka")),
            core=_as_str_list(raw.get("core")),
            on_demand=load_on_demand_list(raw),
            include_global=bool(include),
            notes=notes,
            roles=_as_str_list(raw.get("roles")),
            imports=load_import_records(raw),
            skills=_as_str_list(raw.get("skills")),
            raw=dict(raw),
        )
    return projects


def load_import_records(raw: dict[str, Any]) -> list[ImportRecord]:
    items = raw.get("imports") or []
    records: list[ImportRecord] = []
    if not isinstance(items, list):
        return records
    for item in items:
        if not isinstance(item, dict):
            continue
        pack = item.get("pack")
        version = item.get("version")
        if not pack or not version:
            continue
        stanzas = item["stanzas"] if "stanzas" in item else None
        skills = item["skills"] if "skills" in item else None
        on_demand = item["on_demand"] if "on_demand" in item else None
        records.append(
            ImportRecord(
                pack=str(pack),
                version=str(version),
                stanzas=_as_str_list(stanzas) if stanzas is not None else None,
                skills=_as_str_list(skills) if skills is not None else None,
                on_demand=_as_str_list(on_demand) if on_demand is not None else None,
            )
        )
    return records


def load_pack_repos(root: str | Path) -> list[PackRepo]:
    vault_root = Path(root).resolve()
    path = vault_root / "config" / "pack-repos.yaml"
    if not path.is_file():
        return []
    data = read_yaml(path)
    if not isinstance(data, dict):
        return []
    rows = data.get("repos") or []
    if not isinstance(rows, list):
        return []
    repos: list[PackRepo] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        raw_path = str(row.get("path") or "").strip()
        if not name or not raw_path:
            continue
        repo_path = Path(raw_path)
        if not repo_path.is_absolute():
            repo_path = (vault_root / repo_path).resolve()
        repos.append(PackRepo(name=name, path=repo_path))
    return repos


def _load_lock(root: Path) -> dict[str, Any]:
    path = root / "library" / "lock.yaml"
    if not path.is_file():
        return {}
    data = read_yaml(path)
    return data if isinstance(data, dict) else {}


def _load_pack_role(pack_id: str, version_root: Path) -> Role | None:
    path = version_root / "roles" / f"{pack_id}.yaml"
    if not path.is_file():
        return None
    raw = read_yaml(path)
    if not isinstance(raw, dict):
        raw = {}
    return Role(
        id=pack_id,
        path=path,
        name=str(raw["name"]) if raw.get("name") else None,
        description=str(raw["description"]) if raw.get("description") else None,
        core=_as_str_list(raw.get("core")),
        on_demand=load_on_demand_list(raw),
        raw=dict(raw),
    )


def _load_pack_version(
    pack_id: str, version: str, version_root: Path, lock: dict[str, Any]
) -> PackVersion:
    pack_yaml = {}
    pack_path = version_root / "pack.yaml"
    if pack_path.is_file():
        loaded = read_yaml(pack_path)
        if isinstance(loaded, dict):
            pack_yaml = loaded
    source = None
    pack_lock = lock.get(pack_id) or {}
    if isinstance(pack_lock, dict):
        row = pack_lock.get(version) or {}
        if isinstance(row, dict) and row.get("source"):
            source = str(row["source"])
    return PackVersion(
        pack_id=pack_id,
        version=version,
        path=version_root,
        source=source,
        stanzas=load_stanzas_tree(version_root / "stanzas"),
        role=_load_pack_role(pack_id, version_root),
        pack_yaml=pack_yaml,
        skills=_load_skills(version_root),
    )


def _load_library(
    root: Path,
) -> tuple[dict[str, dict[str, PackVersion]], dict[str, Any]]:
    lock = _load_lock(root)
    library: dict[str, dict[str, PackVersion]] = {}
    lib_root = root / "library"
    if not lib_root.is_dir():
        return library, lock
    for pack_dir in sorted(p for p in lib_root.iterdir() if p.is_dir()):
        try:
            pack_id = validate_pack_id(pack_dir.name)
        except InvalidIdentity:
            continue
        versions: dict[str, PackVersion] = {}
        for version_dir in sorted(p for p in pack_dir.iterdir() if p.is_dir()):
            try:
                version = validate_pack_version(version_dir.name)
            except InvalidIdentity:
                continue
            if version == "latest":
                continue
            versions[version] = _load_pack_version(pack_id, version, version_dir, lock)
        if versions:
            library[pack_id] = versions
    return library, lock


SKILL_PAYLOAD_DIRS = ("scripts", "references")


def skill_payload_paths(skill_dir: Path) -> list[str]:
    rows: list[str] = []
    for folder_name in SKILL_PAYLOAD_DIRS:
        folder = skill_dir / folder_name
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "__pycache__" or "__pycache__" in path.parts:
                continue
            rows.append(path.relative_to(skill_dir).as_posix())
    return rows


def _load_skills(root: Path) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    skills_root = root / "skills"
    if not skills_root.is_dir():
        return skills
    for child in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            skill_id = validate_skill_id(child.name)
        except InvalidIdentity:
            continue
        post = read_frontmatter(skill_md)
        meta = dict(post.metadata or {})
        name = str(meta["name"]) if meta.get("name") else ""
        description = str(meta["description"]) if meta.get("description") else ""
        skills[skill_id] = Skill(
            id=skill_id,
            path=skill_md,
            name=name,
            description=description,
            content=_normalize_body(post.content or ""),
            frontmatter=meta,
            payload=skill_payload_paths(child),
        )
    return skills


def _load_roles(root: Path) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    roles_root = root / "roles"
    if not roles_root.is_dir():
        return roles
    for path in sorted(p for p in roles_root.iterdir() if p.is_file()):
        if path.suffix.lower() != ".yaml":
            continue
        try:
            role_id = validate_role_id(path.stem)
        except InvalidIdentity:
            continue
        raw = read_yaml(path)
        if not isinstance(raw, dict):
            raw = {}
        roles[role_id] = Role(
            id=role_id,
            path=path,
            name=str(raw["name"]) if raw.get("name") else None,
            description=str(raw["description"]) if raw.get("description") else None,
            core=_as_str_list(raw.get("core")),
            on_demand=load_on_demand_list(raw),
            raw=dict(raw),
        )
    return roles
