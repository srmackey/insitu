"""Harvest a product public contract from provisions/pack.yaml onto the shelf."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from insitu.identity import (
    InvalidIdentity,
    validate_article_id,
    validate_pack_id,
    validate_pack_version,
    validate_skill_id,
)
from insitu.library import (
    _after_fetch,
    _bytes_would_change,
    _identity_error,
    _preview_gate,
    _set_lock_source,
    _write_lock,
    copy_pack_interior,
)
from insitu.models import Vault
from insitu.store import load_vault


MANIFEST = "provisions/pack.yaml"


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def _read_manifest(root: Path) -> dict[str, Any] | dict:
    path = root / "provisions" / "pack.yaml"
    if not path.is_file():
        return {
            "ok": True,
            "harvested": False,
            "reason": "no_manifest",
            "path": str(path),
        }
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {"ok": False, "error": "invalid_manifest", "reason": str(exc)}
    if not isinstance(raw, dict):
        return {"ok": False, "error": "invalid_manifest", "reason": "pack.yaml is not a map"}
    return raw


def _member_list(raw: dict[str, Any], key: str) -> list[tuple[str, str]] | dict:
    items = raw.get(key) or []
    if items and not isinstance(items, list):
        return {"ok": False, "error": "invalid_manifest", "reason": f"{key} must be a list"}
    out: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            return {
                "ok": False,
                "error": "extract_list_needs_path",
                "reason": f"{key} members need id and path, not a bare id",
            }
        if not isinstance(item, dict) or "id" not in item or "path" not in item:
            return {
                "ok": False,
                "error": "extract_list_needs_path",
                "reason": f"{key} members need id and path",
            }
        out.append((str(item["id"]), str(item["path"])))
    return out


def _stage_pack(product: Path, raw: dict[str, Any], dest: Path) -> dict | None:
    articles = _member_list(raw, "articles")
    if isinstance(articles, dict):
        return articles
    skills = _member_list(raw, "skills")
    if isinstance(skills, dict):
        return skills
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for article_id, rel in articles:
        try:
            validate_article_id(article_id)
        except InvalidIdentity as exc:
            return _identity_error(article_id, exc)
        src = (product / rel).resolve()
        if not src.is_file():
            return {
                "ok": False,
                "error": "member_missing",
                "id": article_id,
                "path": rel,
            }
        target = dest / "articles" / Path(*article_id.split("/")).with_suffix(".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    for skill_id, rel in skills:
        try:
            validate_skill_id(skill_id)
        except InvalidIdentity as exc:
            return _identity_error(skill_id, exc)
        src = (product / rel).resolve()
        if src.is_file():
            src = src.parent
        if not src.is_dir():
            return {
                "ok": False,
                "error": "member_missing",
                "id": skill_id,
                "path": rel,
            }
        target = dest / "skills" / skill_id
        shutil.copytree(src, target)
    shelf_yaml = {
        "id": raw["id"],
        "name": raw.get("name") or raw["id"],
        "kind": raw.get("kind") or "theme",
        "version": raw["version"],
        "articles": [item[0] for item in articles],
        "skills": [item[0] for item in skills],
    }
    (dest / "pack.yaml").write_text(
        yaml.safe_dump(shelf_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (dest / "VERSION").write_text(str(raw["version"]).strip() + "\n", encoding="utf-8")
    return None


def harvest_provisions(
    vault_or_root: Vault | Path | str,
    working_folder: str | Path,
    *,
    confirm: bool = False,
    expected: dict | None = None,
) -> dict:
    """Seed the shelf from a product's provisions/pack.yaml. No map change."""
    product = Path(working_folder)
    raw = _read_manifest(product)
    if raw.get("harvested") is False or raw.get("ok") is False:
        return raw
    pack_id = raw.get("id")
    version = raw.get("version")
    if not pack_id or not version:
        return {
            "ok": False,
            "error": "invalid_manifest",
            "reason": "id and version are required",
        }
    try:
        pack_id = validate_pack_id(str(pack_id))
        version = validate_pack_version(str(version))
    except InvalidIdentity as exc:
        return _identity_error(str(pack_id), exc)
    vault = _as_vault(vault_or_root)
    dest = vault.root / "library" / pack_id / version
    staging = Path(tempfile.mkdtemp(prefix="insitu-harvest-"))
    try:
        staged = staging / "pack"
        err = _stage_pack(product, raw, staged)
        if err is not None:
            return err
        if dest.is_dir() and not confirm:
            if _bytes_would_change(staged, dest):
                return {
                    "ok": True,
                    "written": False,
                    "expected": {
                        "pack": pack_id,
                        "version": version,
                        "refresh": True,
                    },
                }
            result = _after_fetch(
                vault, pack_id, version, path=str(dest), refreshed=False, source="harvest"
            )
            result["harvested"] = False
            result["reason"] = "already_present"
            result["first_harvest"] = False
            return result
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
        existed = dest.is_dir()
        copy_pack_interior(staged, dest)
        lock = dict(vault.lock)
        _set_lock_source(lock, pack_id, version, "harvest")
        _write_lock(vault.root, lock)
        vault = load_vault(vault.root)
        result = _after_fetch(
            vault,
            pack_id,
            version,
            path=str(dest),
            refreshed=existed,
            source="harvest",
        )
        result["harvested"] = True
        result["first_harvest"] = not bool(result.get("used_by"))
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)
