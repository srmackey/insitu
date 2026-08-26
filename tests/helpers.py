from __future__ import annotations

import shutil
from pathlib import Path

import yaml

FIXTURE_PACKS = Path(__file__).resolve().parent / "fixtures" / "packs"


def fixture_pack(pack_id: str, version: str) -> Path:
    return FIXTURE_PACKS / pack_id / version


def seed_pack_repo(repo_root: Path, pack_id: str, version: str) -> Path:
    src = fixture_pack(pack_id, version)
    dest = repo_root / pack_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def write_pack_repos(vault: Path, repos: list[dict] | None) -> Path:
    folder = vault / "config"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "pack-repos.yaml"
    if repos is None:
        if path.exists():
            path.unlink()
        return path
    path.write_text(
        yaml.safe_dump({"repos": list(repos)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def write_stanza(
    vault: Path,
    stanza_id: str,
    body: str,
    *,
    title: str | None = "Title",
    description: str | None = "Description",
    tags: list[str] | None = None,
    include_id: bool = True,
    extra_fm: dict | None = None,
) -> Path:
    rel = Path(*stanza_id.split("/"))
    path = vault / "stanzas" / rel.with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    meta: dict = {}
    if include_id:
        meta["id"] = stanza_id
    if title is not None:
        meta["title"] = title
    if description is not None:
        meta["description"] = description
    if tags:
        meta["tags"] = tags
    if extra_fm:
        meta.update(extra_fm)
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n"
    text += body if body.endswith("\n") else body + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def write_project(
    vault: Path,
    key: str,
    *,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    available: list[str] | None = None,
    roles: list[str] | None = None,
    include_global: bool | None = None,
    repo: str | None = None,
    name: str | None = None,
    aka: list[str] | None = None,
    notes: str | None = None,
    imports: list[dict] | None = None,
    skills: list[str] | None = None,
) -> Path:
    folder = vault / "projects" / key
    folder.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if repo is not None:
        data["repo"] = repo
    if name is not None:
        data["name"] = name
    if aka is not None:
        data["aka"] = aka
    if roles is not None:
        data["roles"] = list(roles)
    data["core"] = list(core or [])
    if available is not None:
        data["available"] = list(available)
    else:
        data["on_demand"] = list(on_demand or [])
    if include_global is not None:
        data["include_global"] = include_global
    if imports is not None:
        data["imports"] = list(imports)
    if skills:
        data["skills"] = list(skills)
    (folder / "map.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    if notes is not None:
        (folder / "notes.md").write_text(notes, encoding="utf-8")
    return folder


def write_role(
    vault: Path,
    role_id: str,
    *,
    core: list[str] | None = None,
    on_demand: list[str] | None = None,
    available: list[str] | None = None,
    name: str | None = None,
    description: str | None = None,
    extra: dict | None = None,
) -> Path:
    folder = vault / "roles"
    folder.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    data["core"] = list(core or [])
    if available is not None:
        data["available"] = list(available)
    else:
        data["on_demand"] = list(on_demand or [])
    if extra:
        data.update(extra)
    path = folder / f"{role_id}.yaml"
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def write_skill(
    vault: Path,
    skill_id: str,
    body: str,
    *,
    name: str | None = None,
    description: str | None = "Close the day's books.",
    extra_fm: dict | None = None,
    payload: dict[str, str] | None = None,
    extra_files: dict[str, str] | None = None,
) -> Path:
    folder = vault / "skills" / skill_id
    folder.mkdir(parents=True, exist_ok=True)
    meta: dict = {}
    meta["name"] = skill_id if name is None else name
    if description is not None:
        meta["description"] = description
    if extra_fm:
        meta.update(extra_fm)
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n"
    text += body if body.endswith("\n") else body + "\n"
    path = folder / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    for rel, content in (payload or {}).items():
        dest = folder / Path(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    for rel, content in (extra_files or {}).items():
        dest = folder / Path(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return path
