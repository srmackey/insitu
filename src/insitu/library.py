"""Pack shelf: pull, install, fetch, remove, inventory (DESIGN.md §6.2)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from insitu.identity import (
    InvalidIdentity,
    validate_pack_id,
    validate_pack_version,
    validate_project_key,
    validate_skill_id,
    validate_article_id,
    version_sort_key,
)
from insitu.models import ImportRecord, PackVersion, Vault
from insitu.provisions import (
    composed_articles,
    composed_ids,
    conflict_refusal,
    conflicts_between,
    conflicts_within,
    mentions_not_composed,
    prohibition_refusal,
)
from insitu.store import load_pack_repos, load_vault

INTERIOR_FILES = ("pack.yaml", "VERSION")
INTERIOR_DIRS = ("articles", "roles", "skills")


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


def _preview_gate(confirm: bool, expected: dict | None, plan: dict) -> dict | None:
    from insitu.affects import expected_matches

    if not confirm:
        return {**plan, "ok": True, "written": False}
    if expected is None:
        return {"ok": False, "error": "missing_expected"}
    if not expected_matches(plan.get("expected", {}), expected):
        return {**plan, "ok": False, "error": "stale_preview", "written": False}
    return None


def newest_version(versions: list[str]) -> str | None:
    numbered = [item for item in versions if item != "latest"]
    if not numbered:
        return None
    return max(numbered, key=version_sort_key)


def read_version_file(pack_root: Path) -> str | None:
    path = pack_root / "VERSION"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return text.splitlines()[0].strip()


def repo_pack_root(vault: Vault, pack_id: str, repo_name: str | None = None) -> tuple[Path, str] | None:
    repos = vault.pack_repos
    if repo_name is not None:
        repos = [item for item in repos if item.name == repo_name]
        if not repos:
            return None
    for repo in repos:
        root = repo.path / pack_id
        current = read_version_file(root)
        if current is None:
            continue
        return root, repo.name
    return None


def available_versions(vault: Vault, pack_id: str) -> list[str]:
    found: set[str] = set(vault.library.get(pack_id, {}))
    for repo in vault.pack_repos:
        current = read_version_file(repo.path / pack_id)
        if current:
            found.add(current)
    return sorted(found, key=version_sort_key)


def version_missing(pack_id: str, version: str, available: list[str]) -> dict:
    result: dict[str, Any] = {
        "ok": False,
        "error": "version_missing",
        "pack": pack_id,
        "version": version,
        "available": list(available),
    }
    default = newest_version(available)
    if default is not None:
        result["default"] = default
    return result


def record_member_ids(record: ImportRecord, pack: PackVersion, field: str) -> list[str]:
    if record.is_capability():
        if field == "skills":
            return []
        if pack.role is not None:
            return list(getattr(pack.role, field))
        if field == "core":
            return [str(item) for item in (pack.pack_yaml.get("articles") or [])]
        return []
    if field == "on_demand":
        return list(record.on_demand or [])
    if field == "skills":
        return list(record.skills or [])
    return list(record.articles or [])


def cited_versions(vault: Vault) -> set[tuple[str, str]]:
    cited: set[tuple[str, str]] = set()
    for proj in vault.projects.values():
        for record in proj.imports:
            if record.version == "latest":
                newest = newest_version(list(vault.library.get(record.pack, {})))
                if newest is not None:
                    cited.add((record.pack, newest))
                continue
            cited.add((record.pack, record.version))
    return cited


def copy_pack_interior(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name in INTERIOR_FILES:
        file = src / name
        if file.is_file():
            shutil.copy2(file, dest / name)
    for name in INTERIOR_DIRS:
        folder = src / name
        if folder.is_dir():
            shutil.copytree(folder, dest / name)


def _write_lock(vault_root: Path, lock: dict[str, Any]) -> None:
    folder = vault_root / "library"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "lock.yaml"
    path.write_text(
        yaml.safe_dump(lock, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _set_lock_source(lock: dict[str, Any], pack_id: str, version: str, source: str) -> None:
    pack_lock = lock.get(pack_id)
    if not isinstance(pack_lock, dict):
        pack_lock = {}
        lock[pack_id] = pack_lock
    pack_lock[version] = {"source": source}


def _drop_lock_version(lock: dict[str, Any], pack_id: str, version: str) -> None:
    pack_lock = lock.get(pack_id)
    if not isinstance(pack_lock, dict):
        return
    pack_lock.pop(version, None)
    if not pack_lock:
        lock.pop(pack_id, None)


def _write_map_imports(proj_path: Path, raw: dict[str, Any], records: list[ImportRecord]) -> None:
    data = dict(raw)
    if records:
        data["imports"] = [item.as_dict() for item in records]
    else:
        data.pop("imports", None)
    (proj_path / "map.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _find_source(
    vault: Vault,
    pack_id: str,
    version: str,
    *,
    repo: str | None = None,
    path: str | Path | None = None,
) -> tuple[Path, str] | dict:
    if path is not None:
        src = Path(path)
        current = read_version_file(src)
        if current != version:
            return version_missing(pack_id, version, [current] if current else [])
        return src, "path"
    hit = repo_pack_root(vault, pack_id, repo_name=repo)
    if hit is None:
        return version_missing(pack_id, version, available_versions(vault, pack_id))
    src, source_name = hit
    current = read_version_file(src)
    if current != version:
        available = available_versions(vault, pack_id)
        return version_missing(pack_id, version, available)
    return src, source_name


def pull_pack_version(
    vault_or_root: Vault | Path | str,
    pack_id: str,
    version: str,
    *,
    repo: str | None = None,
    path: str | Path | None = None,
    refresh: bool = False,
) -> dict:
    try:
        pack_id = validate_pack_id(pack_id)
        version = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(pack_id if isinstance(pack_id, str) else version, exc)
    if version == "latest":
        return {"ok": False, "error": "invalid_identity", "value": version}
    vault = _as_vault(vault_or_root)
    existing = vault.library.get(pack_id, {}).get(version)
    if existing is not None and path is None and not refresh:
        # Already on the shelf and no refresh asked for. `refresh` has to be
        # part of this guard: without it a confirmed fetch_pack refresh from a
        # configured repo returned ok with nothing written, because only an
        # explicit `path` defeated the short-circuit.
        return {
            "ok": True,
            "pulled": False,
            "reason": "already_present",
            "pack": pack_id,
            "version": version,
            "path": str(existing.path),
        }
    found = _find_source(vault, pack_id, version, repo=repo, path=path)
    if isinstance(found, dict):
        return found
    src, source_name = found
    dest = vault.root / "library" / pack_id / version
    copy_pack_interior(src, dest)
    lock = dict(vault.lock)
    _set_lock_source(lock, pack_id, version, source_name)
    _write_lock(vault.root, lock)
    return {
        "ok": True,
        "pulled": True,
        "pack": pack_id,
        "version": version,
        "path": str(dest),
        "source": source_name,
    }


def sync_latest(vault_or_root: Vault | Path | str, pack_id: str) -> bool:
    vault = _as_vault(vault_or_root)
    available = available_versions(vault, pack_id)
    newest = newest_version(available)
    if newest is None:
        return False
    if newest in vault.library.get(pack_id, {}):
        return False
    result = pull_pack_version(vault, pack_id, newest)
    return bool(result.get("ok") and result.get("pulled"))


def concrete_version(vault: Vault, record: ImportRecord) -> str | dict:
    if record.version == "latest":
        newest = newest_version(available_versions(vault, record.pack))
        if newest is None:
            return version_missing(record.pack, "latest", [])
        return newest
    if record.version in vault.library.get(record.pack, {}):
        return record.version
    return version_missing(
        record.pack, record.version, available_versions(vault, record.pack)
    )


def newer_than_pin(vault: Vault, pack_id: str, pinned: str) -> str | None:
    newest = newest_version(available_versions(vault, pack_id))
    if newest is None or newest == pinned:
        return None
    if version_sort_key(newest) > version_sort_key(pinned):
        return newest
    return None


def fetch_pack(
    vault_or_root: Path | str | Vault,
    pack_id: str,
    version: str,
    *,
    repo: str | None = None,
    path: str | None = None,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    try:
        pack_id = validate_pack_id(pack_id)
        version = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(pack_id, exc)
    vault = _as_vault(vault_or_root)
    dest = vault.root / "library" / pack_id / version
    if dest.is_dir() and not confirm:
        found = _find_source(vault, pack_id, version, repo=repo, path=path)
        if isinstance(found, dict):
            return {
                "ok": True,
                "pack": pack_id,
                "version": version,
                "path": str(dest),
                "refreshed": False,
            }
        src, _source = found
        if _bytes_would_change(src, dest):
            plan = {
                "ok": True,
                "written": False,
                "expected": {"pack": pack_id, "version": version, "refresh": True},
            }
            return plan
        return {
            "ok": True,
            "pack": pack_id,
            "version": version,
            "path": str(dest),
            "refreshed": False,
        }
    if dest.is_dir() and confirm:
        gated = _preview_gate(
            confirm,
            expected,
            {
                "ok": True,
                "written": False,
                "expected": {"pack": pack_id, "version": version, "refresh": True},
            },
        )
        if gated is not None:
            return gated
    pulled = pull_pack_version(
        vault, pack_id, version, repo=repo, path=path, refresh=confirm
    )
    if not pulled.get("ok"):
        return pulled
    return {
        "ok": True,
        "pack": pack_id,
        "version": version,
        "path": pulled["path"],
        "source": pulled.get("source"),
        "refreshed": bool(pulled.get("pulled")),
    }


def _bytes_would_change(src: Path, dest: Path) -> bool:
    for name in INTERIOR_FILES:
        left = src / name
        right = dest / name
        if left.is_file() != right.is_file():
            return True
        if left.is_file() and left.read_bytes() != right.read_bytes():
            return True
    for name in INTERIOR_DIRS:
        left = src / name
        right = dest / name
        if left.is_dir() != right.is_dir():
            return True
        if not left.is_dir():
            continue
        left_files = {p.relative_to(left).as_posix(): p for p in left.rglob("*") if p.is_file()}
        right_files = {p.relative_to(right).as_posix(): p for p in right.rglob("*") if p.is_file()}
        if set(left_files) != set(right_files):
            return True
        for rel, path in left_files.items():
            if path.read_bytes() != right_files[rel].read_bytes():
                return True
    return False


def _resolve_install_version(
    vault: Vault, pack_id: str, version: str
) -> tuple[Vault, str] | dict:
    if version == "latest":
        sync_latest(vault, pack_id)
        vault = load_vault(vault.root)
        newest = newest_version(available_versions(vault, pack_id))
        if newest is None:
            return version_missing(pack_id, "latest", [])
        if newest not in vault.library.get(pack_id, {}):
            pulled = pull_pack_version(vault, pack_id, newest)
            if not pulled.get("ok"):
                return pulled
            vault = load_vault(vault.root)
        return vault, newest
    if version in vault.library.get(pack_id, {}):
        return vault, version
    pulled = pull_pack_version(vault, pack_id, version)
    if not pulled.get("ok"):
        return pulled
    return load_vault(vault.root), version


def _append_capability(records: list[ImportRecord], pack_id: str, version: str) -> list[ImportRecord]:
    kept: list[ImportRecord] = []
    replaced = False
    for record in records:
        if record.pack == pack_id and record.version == version:
            if not replaced:
                kept.append(ImportRecord(pack=pack_id, version=version))
                replaced = True
            continue
        kept.append(record)
    if not replaced:
        kept.append(ImportRecord(pack=pack_id, version=version))
    return kept


def _append_article(
    records: list[ImportRecord],
    pack_id: str,
    version: str,
    article_id: str,
    target: str = "core",
) -> list[ImportRecord] | dict:
    for record in records:
        if record.pack == pack_id and record.version == version and record.is_capability():
            return records
    updated: list[ImportRecord] = []
    added = False
    for record in records:
        if (
            record.pack == pack_id
            and record.version == version
            and not record.is_capability()
            and not added
        ):
            articles = list(record.articles) if record.articles is not None else None
            on_demand = list(record.on_demand) if record.on_demand is not None else None
            if target == "on_demand":
                on_demand = on_demand or []
                if article_id not in on_demand:
                    on_demand.append(article_id)
            else:
                articles = articles or []
                if article_id not in articles:
                    articles.append(article_id)
            updated.append(
                ImportRecord(
                    pack=pack_id,
                    version=version,
                    articles=articles,
                    skills=record.skills,
                    on_demand=on_demand,
                )
            )
            added = True
            continue
        updated.append(record)
    if not added:
        field = "on_demand" if target == "on_demand" else "articles"
        updated.append(
            ImportRecord(pack=pack_id, version=version, **{field: [article_id]})
        )
    seen: set[str] = set()
    for record in updated:
        if record.is_capability():
            continue
        members = record.article_members()
        for sid in members:
            if sid in seen and sid == article_id:
                return {
                    "ok": False,
                    "error": "duplicate_import_article",
                    "id": sid,
                    "pack": pack_id,
                }
            seen.add(sid)
    return updated


def install_capability(
    vault_or_root: Path | str | Vault,
    project: str,
    pack: str,
    version: str,
) -> dict:
    try:
        key = validate_project_key(project)
        pack_id = validate_pack_id(pack)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    resolved = _resolve_install_version(vault, pack_id, requested)
    if isinstance(resolved, dict):
        return resolved
    vault, concrete = resolved
    shelved = vault.library[pack_id][concrete]
    if str(shelved.pack_yaml.get("kind") or "").strip().lower() == "theme":
        # A theme pack is a menu. Its members are meant to be taken one at a
        # time, so a whole-capability subscribe is a request the pack cannot
        # answer. Name the members rather than silently installing nothing.
        return {
            "ok": False,
            "error": "theme_pack_not_capability",
            "pack": pack_id,
            "version": concrete,
            "members": sorted(shelved.articles),
            "skills": sorted(shelved.skills),
            "detail": "install members individually with install_article or install_skill",
        }
    proj = vault.projects[key]
    arriving = [shelved.articles[aid] for aid in sorted(shelved.articles)]
    for article in arriving:
        banned = prohibition_refusal(vault, key, article.id)
        if banned is not None:
            banned.update({"pack": pack_id, "version": concrete})
            return banned
    already = composed_articles(vault, key)
    for article in arriving:
        clash = conflicts_between(article, already)
        if clash:
            return {
                "ok": False,
                "error": "conflicts_with_composed",
                "id": article.id,
                "project": key,
                "pack": pack_id,
                "version": concrete,
                "conflicts": clash,
            }
    internal = conflicts_within(arriving)
    if internal:
        # The pack cannot be installed whole at all: two of its own members
        # declare against each other, so no project could compose it. That is a
        # defect in the pack, not in this map, and it is named as one.
        return {
            "ok": False,
            "error": "pack_conflicts_internally",
            "project": key,
            "pack": pack_id,
            "version": concrete,
            "conflicts": internal,
        }
    stored_version = requested
    records = _append_capability(list(proj.imports), pack_id, stored_version)
    _write_map_imports(proj.path, proj.raw, records)
    result: dict[str, Any] = {
        "ok": True,
        "project": key,
        "pack": pack_id,
        "version": stored_version,
        "resolved_version": concrete,
    }
    have = composed_ids(vault, key) | {article.id for article in arriving}
    mentions = mentions_not_composed(
        vault,
        [text for article in arriving for text in (article.description, article.content)],
        have,
        pack=shelved,
    )
    if mentions:
        result["mentions_not_composed"] = mentions
    newer = newer_than_pin(vault, pack_id, concrete) if stored_version != "latest" else None
    if newer:
        result["newer_available"] = [{"pack": pack_id, "pinned": concrete, "newer": newer}]
    return result


def _infer_pack(vault: Vault, article_id: str, version: str) -> str | dict:
    matches: list[str] = []
    for pack_id, versions in vault.library.items():
        pack = versions.get(version)
        if pack is not None and article_id in pack.articles and pack_id not in matches:
            matches.append(pack_id)
    for repo in vault.pack_repos:
        if not repo.path.is_dir():
            continue
        for child in repo.path.iterdir():
            if not child.is_dir():
                continue
            try:
                pack_id = validate_pack_id(child.name)
            except InvalidIdentity:
                continue
            current = read_version_file(child)
            if current != version:
                continue
            article_path = child / "articles" / Path(*article_id.split("/")).with_suffix(".md")
            if article_path.is_file() and pack_id not in matches:
                matches.append(pack_id)
    if len(matches) == 1:
        return matches[0]
    return {
        "ok": False,
        "error": "ambiguous_pack" if matches else "version_missing",
        "id": article_id,
        "version": version,
        "packs": matches,
    }


def install_article(
    vault_or_root: Path | str | Vault,
    project: str,
    article_id: str,
    version: str,
    pack: str | None = None,
    target: str = "core",
) -> dict:
    try:
        key = validate_project_key(project)
        sid = validate_article_id(article_id)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(article_id, exc)
    if target not in {"core", "on_demand"}:
        return {"ok": False, "error": "invalid_target", "value": target}
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    pack_id: str
    if pack is None:
        probe_version = requested
        if requested == "latest":
            probe_version = newest_version(available_versions(vault, "")) or requested
        inferred = _infer_pack(vault, sid, probe_version)
        if isinstance(inferred, dict):
            return inferred
        pack_id = inferred
    else:
        try:
            pack_id = validate_pack_id(pack)
        except InvalidIdentity as exc:
            return _identity_error(pack, exc)
    resolved = _resolve_install_version(vault, pack_id, requested)
    if isinstance(resolved, dict):
        return resolved
    vault, concrete = resolved
    pack_ver = vault.library.get(pack_id, {}).get(concrete)
    if pack_ver is None or sid not in pack_ver.articles:
        return {"ok": False, "error": "missing_article", "id": sid, "pack": pack_id, "version": concrete}
    proj = vault.projects[key]
    installed = pack_ver.articles[sid]
    banned = prohibition_refusal(vault, key, sid)
    if banned is not None:
        banned.update({"pack": pack_id, "version": concrete})
        return banned
    clash = conflict_refusal(vault, key, installed)
    if clash is not None:
        clash.update({"pack": pack_id, "version": concrete})
        return clash
    have = composed_ids(vault, key) | {sid}
    records = _append_article(list(proj.imports), pack_id, requested, sid, target)
    if isinstance(records, dict):
        return records
    _write_map_imports(proj.path, proj.raw, records)
    result: dict[str, Any] = {
        "ok": True,
        "project": key,
        "pack": pack_id,
        "version": requested,
        "resolved_version": concrete,
        "article": sid,
        "target": target,
        "title": installed.title,
        "description": installed.description,
    }
    mentions = mentions_not_composed(
        vault, [installed.description, installed.content], have, pack=pack_ver
    )
    if mentions:
        result["mentions_not_composed"] = mentions
    return result


def uninstall_capability(
    vault_or_root: Path | str | Vault,
    project: str,
    pack: str,
    version: str,
) -> dict:
    try:
        key = validate_project_key(project)
        pack_id = validate_pack_id(pack)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(project, exc)
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    kept = [
        record
        for record in proj.imports
        if not (
            record.pack == pack_id
            and record.version == requested
            and record.is_capability()
        )
    ]
    _write_map_imports(proj.path, proj.raw, kept)
    return {"ok": True, "project": key, "pack": pack_id, "version": requested}


def uninstall_article(
    vault_or_root: Path | str | Vault,
    project: str,
    article_id: str,
    pack: str,
    version: str,
) -> dict:
    try:
        key = validate_project_key(project)
        sid = validate_article_id(article_id)
        pack_id = validate_pack_id(pack)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(article_id, exc)
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    kept: list[ImportRecord] = []
    for record in proj.imports:
        if record.pack != pack_id or record.version != requested:
            kept.append(record)
            continue
        if record.is_capability():
            kept.append(record)
            continue
        if record.articles is None and record.on_demand is None:
            kept.append(record)
            continue
        articles = (
            [item for item in record.articles if item != sid]
            if record.articles is not None
            else None
        )
        on_demand = (
            [item for item in record.on_demand if item != sid]
            if record.on_demand is not None
            else None
        )
        if not articles and not on_demand and not record.skills:
            continue
        kept.append(
            ImportRecord(
                pack=record.pack,
                version=record.version,
                articles=articles or None,
                skills=record.skills,
                on_demand=on_demand or None,
            )
        )
    _write_map_imports(proj.path, proj.raw, kept)
    return {
        "ok": True,
        "project": key,
        "pack": pack_id,
        "version": requested,
        "article": sid,
    }


def _append_skill(
    records: list[ImportRecord], pack_id: str, version: str, skill_id: str
) -> list[ImportRecord] | dict:
    updated: list[ImportRecord] = []
    added = False
    for record in records:
        if (
            record.pack == pack_id
            and record.version == version
            and not record.is_capability()
            and not added
        ):
            skills = list(record.skills or [])
            if skill_id not in skills:
                skills.append(skill_id)
            updated.append(
                ImportRecord(
                    pack=pack_id,
                    version=version,
                    articles=record.articles,
                    skills=skills,
                    on_demand=record.on_demand,
                )
            )
            added = True
            continue
        updated.append(record)
    if not added:
        updated.append(
            ImportRecord(pack=pack_id, version=version, skills=[skill_id])
        )
    seen: set[str] = set()
    for record in updated:
        if record.is_capability():
            continue
        for sid in record.skills or []:
            if sid in seen and sid == skill_id:
                return {
                    "ok": False,
                    "error": "duplicate_import_skill",
                    "id": sid,
                    "pack": pack_id,
                }
            seen.add(sid)
    return updated


def _infer_pack_skill(vault: Vault, skill_id: str, version: str) -> str | dict:
    matches: list[str] = []
    for pack_id, versions in vault.library.items():
        pack = versions.get(version)
        if pack is not None and skill_id in pack.skills and pack_id not in matches:
            matches.append(pack_id)
    for repo in vault.pack_repos:
        if not repo.path.is_dir():
            continue
        for child in repo.path.iterdir():
            if not child.is_dir():
                continue
            try:
                pack_id = validate_pack_id(child.name)
            except InvalidIdentity:
                continue
            current = read_version_file(child)
            if current != version:
                continue
            skill_path = child / "skills" / skill_id / "SKILL.md"
            if skill_path.is_file() and pack_id not in matches:
                matches.append(pack_id)
    if len(matches) == 1:
        return matches[0]
    return {
        "ok": False,
        "error": "ambiguous_pack" if matches else "version_missing",
        "id": skill_id,
        "version": version,
        "packs": matches,
    }


def install_skill(
    vault_or_root: Path | str | Vault,
    project: str,
    skill_id: str,
    version: str,
    pack: str | None = None,
) -> dict:
    try:
        key = validate_project_key(project)
        sid = validate_skill_id(skill_id)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    pack_id: str
    if pack is None:
        target = requested
        if requested == "latest":
            target = newest_version(available_versions(vault, "")) or requested
        inferred = _infer_pack_skill(vault, sid, target)
        if isinstance(inferred, dict):
            return inferred
        pack_id = inferred
    else:
        try:
            pack_id = validate_pack_id(pack)
        except InvalidIdentity as exc:
            return _identity_error(pack, exc)
    resolved = _resolve_install_version(vault, pack_id, requested)
    if isinstance(resolved, dict):
        return resolved
    vault, concrete = resolved
    pack_ver = vault.library.get(pack_id, {}).get(concrete)
    if pack_ver is None or sid not in pack_ver.skills:
        return {
            "ok": False,
            "error": "missing_skill",
            "id": sid,
            "pack": pack_id,
            "version": concrete,
        }
    proj = vault.projects[key]
    installed = pack_ver.skills[sid]
    records = _append_skill(list(proj.imports), pack_id, requested, sid)
    if isinstance(records, dict):
        return records
    _write_map_imports(proj.path, proj.raw, records)
    result: dict[str, Any] = {
        "ok": True,
        "project": key,
        "pack": pack_id,
        "version": requested,
        "resolved_version": concrete,
        "skill": sid,
    }
    # A skill is often the hands to an article's governance, so the article it
    # serves is the companion most worth naming here.
    mentions = mentions_not_composed(
        vault,
        [installed.description, installed.content],
        composed_ids(vault, key),
        pack=pack_ver,
    )
    if mentions:
        result["mentions_not_composed"] = mentions
    return result


def uninstall_skill(
    vault_or_root: Path | str | Vault,
    project: str,
    skill_id: str,
    pack: str,
    version: str,
) -> dict:
    try:
        key = validate_project_key(project)
        sid = validate_skill_id(skill_id)
        pack_id = validate_pack_id(pack)
        requested = validate_pack_version(version)
    except InvalidIdentity as exc:
        return _identity_error(skill_id, exc)
    vault = _as_vault(vault_or_root)
    proj = vault.projects.get(key)
    if proj is None:
        return {"ok": False, "error": "project_missing", "project": key}
    kept: list[ImportRecord] = []
    for record in proj.imports:
        if record.pack != pack_id or record.version != requested:
            kept.append(record)
            continue
        if record.is_capability():
            kept.append(record)
            continue
        if record.skills is None:
            kept.append(record)
            continue
        skills = [item for item in record.skills if item != sid]
        if not skills and not record.article_members():
            continue
        kept.append(
            ImportRecord(
                pack=record.pack,
                version=record.version,
                articles=record.articles,
                skills=skills or None,
                on_demand=record.on_demand,
            )
        )
    _write_map_imports(proj.path, proj.raw, kept)
    return {
        "ok": True,
        "project": key,
        "pack": pack_id,
        "version": requested,
        "skill": sid,
    }


def _projects_using(vault: Vault, pack_id: str, versions: set[str]) -> list[str]:
    used: list[str] = []
    for key, proj in vault.projects.items():
        for record in proj.imports:
            if record.version == "latest":
                newest = newest_version(list(vault.library.get(record.pack, {})))
                if newest is not None and record.pack == pack_id and newest in versions:
                    used.append(key)
                    break
            elif record.pack == pack_id and record.version in versions:
                used.append(key)
                break
    return used


def remove_pack(
    vault_or_root: Path | str | Vault,
    pack: str,
    version: str | None = None,
    *,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    try:
        pack_id = validate_pack_id(pack)
        requested = validate_pack_version(version) if version is not None else None
    except InvalidIdentity as exc:
        return _identity_error(pack, exc)
    vault = _as_vault(vault_or_root)
    on_disk = list(vault.library.get(pack_id, {}))
    if requested is not None:
        versions = [requested] if requested in on_disk else []
        if requested not in on_disk:
            return {"ok": False, "error": "not_found", "pack": pack_id, "version": requested}
    else:
        versions = list(on_disk)
    projects = _projects_using(vault, pack_id, set(versions))
    plan = {
        "ok": True,
        "written": False,
        "expected": {
            "pack": pack_id,
            "versions": list(versions),
            "projects": list(projects),
        },
    }
    gated = _preview_gate(confirm, expected, plan)
    if gated is not None:
        return gated
    lock = dict(vault.lock)
    for ver in versions:
        dest = vault.root / "library" / pack_id / ver
        if dest.is_dir():
            shutil.rmtree(dest)
        _drop_lock_version(lock, pack_id, ver)
    pack_dir = vault.root / "library" / pack_id
    if pack_dir.is_dir() and not any(pack_dir.iterdir()):
        pack_dir.rmdir()
    _write_lock(vault.root, lock)
    vault = load_vault(vault.root)
    drop_versions = set(versions)
    for key in projects:
        proj = vault.projects.get(key)
        if proj is None:
            continue
        kept: list[ImportRecord] = []
        for record in proj.imports:
            if record.pack != pack_id:
                kept.append(record)
                continue
            if record.version == "latest":
                newest = newest_version(list(drop_versions) + list(vault.library.get(pack_id, {})))
                if newest in drop_versions and requested is None:
                    continue
                kept.append(record)
                continue
            if record.version in drop_versions:
                continue
            kept.append(record)
        _write_map_imports(proj.path, proj.raw, kept)
    return {**plan, "ok": True, "written": True}


def list_packs(vault_or_root: Path | str | Vault) -> dict:
    vault = _as_vault(vault_or_root)
    cited = cited_versions(vault)
    packs: list[dict] = []
    for pack_id in sorted(vault.library):
        versions = []
        for version in sorted(vault.library[pack_id], key=version_sort_key):
            pack = vault.library[pack_id][version]
            used_by = []
            for key, proj in vault.projects.items():
                for record in proj.imports:
                    matches = record.pack == pack_id and (
                        record.version == version
                        or (
                            record.version == "latest"
                            and newest_version(list(vault.library.get(pack_id, {})))
                            == version
                        )
                    )
                    if not matches:
                        continue
                    if record.is_capability():
                        used_by.append({"project": key, "kind": "capability"})
                    else:
                        used_by.append(
                            {
                                "project": key,
                                "kind": "articles",
                                "articles": record.article_members(),
                            }
                        )
            versions.append(
                {
                    "version": version,
                    "source": pack.source,
                    "used_by": used_by,
                    "unreferenced": (pack_id, version) not in cited,
                }
            )
        packs.append({"id": pack_id, "versions": versions})
    return {"ok": True, "packs": packs}


def get_pack(vault_or_root: Path | str | Vault, pack: str) -> dict:
    try:
        pack_id = validate_pack_id(pack)
    except InvalidIdentity as exc:
        return _identity_error(pack, exc)
    vault = _as_vault(vault_or_root)
    versions = vault.library.get(pack_id)
    if not versions:
        return {"ok": False, "error": "not_found", "id": pack_id}
    listed = list_packs(vault)
    row = next(item for item in listed["packs"] if item["id"] == pack_id)
    members = {
        version: sorted(pack.articles)
        for version, pack in versions.items()
    }
    skill_members = {
        version: sorted(pack.skills)
        for version, pack in versions.items()
    }
    pins = []
    for key, proj in vault.projects.items():
        for record in proj.imports:
            if record.pack == pack_id:
                pins.append({"project": key, **record.as_dict()})
    return {
        "ok": True,
        "id": pack_id,
        "versions": row["versions"],
        "members": members,
        "skill_members": skill_members,
        "pins": pins,
    }
