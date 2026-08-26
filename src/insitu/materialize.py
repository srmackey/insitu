"""Write PROTOCOL.md and host adapters (DESIGN.md §10)."""

from __future__ import annotations

import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from insitu.store import SKILL_PAYLOAD_DIRS, read_yaml, skill_payload_paths

from insitu.identity import InvalidIdentity, validate_project_key
from insitu.models import Skill, Vault
from insitu.resolve import iter_composed_skills, resolve_protocol
from insitu.store import load_vault

KNOWN_SURFACES = {
    "grok": Path(".grok") / "rules" / "insitu-protocol.md",
    "claude": Path(".claude") / "rules" / "insitu-protocol.md",
    "cursor": Path(".cursor") / "rules" / "insitu-protocol.mdc",
}

SKILL_ROOTS = {
    "grok": Path(".grok") / "skills",
    "claude": Path(".claude") / "skills",
    "cursor": Path(".cursor") / "skills",
}

CONSTITUTION_NAMES = frozenset({"AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"})
GIT_TIMEOUT_SECONDS = 15
ADAPTER_WRITE_TIMEOUT_SECONDS = 8


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def vault_git_ref(vault_root: Path) -> str | None:
    if not (vault_root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha or None


def parse_header(text: str) -> dict | None:
    """Parse a materialize generated-file header. None if missing or unparseable."""
    start = text.find("<!--")
    end = text.find("-->")
    if start < 0 or end < 0 or end <= start:
        return None
    block = text[start + 4 : end]
    if "insitu-generated:" not in block:
        return None
    data: dict = {"stanzas": []}
    in_stanzas = False
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_stanzas:
            if line == "-":
                continue
            if line.startswith("- "):
                data["stanzas"].append(line[2:].strip())
                continue
            in_stanzas = False
        if line.startswith("stanzas:"):
            in_stanzas = True
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    if "project" not in data or "timestamp" not in data:
        return None
    return data


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    rest = text[3:]
    marker = rest.find("\n---")
    if marker < 0:
        return text, ""
    fm_end = 3 + marker + 4
    front = text[:fm_end]
    body = text[fm_end:]
    if body.startswith("\n"):
        body = body[1:]
    return front, body


def render_skill_stamp(vault_root: Path, project: str, skill_id: str) -> str:
    git_ref = vault_git_ref(vault_root) or "none"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return "\n".join(
        [
            "<!--",
            "insitu-generated: true",
            f"vault: {vault_root}",
            f"git: {git_ref}",
            f"timestamp: {timestamp}",
            f"project: {project}",
            f"skill: {skill_id}",
            "-->",
        ]
    )


def has_insitu_skill_stamp(text: str) -> bool:
    _front, body = split_frontmatter(text)
    stripped = body.lstrip()
    if not stripped.startswith("<!--"):
        return False
    end = stripped.find("-->")
    if end < 0:
        return False
    block = stripped[:end]
    return "insitu-generated: true" in block and "skill:" in block


def render_skill_copy(vault_text: str, vault_root: Path, project: str, skill_id: str) -> str:
    front, body = split_frontmatter(vault_text)
    stamp = render_skill_stamp(vault_root, project, skill_id)
    if front:
        return front + "\n" + stamp + "\n\n" + body.lstrip("\n")
    return stamp + "\n\n" + body


def _copy_skill_payload(src_dir: Path, dest_dir: Path) -> list[Path]:
    written: list[Path] = []
    for folder_name in SKILL_PAYLOAD_DIRS:
        dest_folder = dest_dir / folder_name
        if dest_folder.exists():
            shutil.rmtree(dest_folder)
        src_folder = src_dir / folder_name
        if not src_folder.is_dir():
            continue
        dest_folder.mkdir(parents=True, exist_ok=True)
        for rel in skill_payload_paths(src_dir):
            if not rel.startswith(folder_name + "/"):
                continue
            src = src_dir / rel
            dest = dest_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            written.append(dest)
    return written


def _write_mapped_skills(
    vault,
    work: Path,
    key: str,
    surfaces: list[str],
    skills: list[Skill],
) -> tuple[list[dict], list[dict]]:
    written_paths: dict[str, list[str]] = {skill.id: [] for skill in skills}
    removed: list[dict] = []
    composed = {skill.id for skill in skills}
    for name in surfaces:
        root = work / SKILL_ROOTS[name]
        if root.is_dir():
            for child in list(root.iterdir()):
                if not child.is_dir():
                    continue
                skill_md = child / "SKILL.md"
                if not skill_md.is_file():
                    continue
                text = skill_md.read_text(encoding="utf-8")
                if has_insitu_skill_stamp(text) and child.name not in composed:
                    shutil.rmtree(child)
                    removed.append(
                        {"surface": name, "id": child.name, "path": str(child)}
                    )
        for skill in skills:
            dest_dir = root / skill.id
            dest_dir.mkdir(parents=True, exist_ok=True)
            vault_text = skill.path.read_text(encoding="utf-8")
            dest_md = dest_dir / "SKILL.md"
            dest_md.write_text(
                render_skill_copy(vault_text, vault.root, key, skill.id),
                encoding="utf-8",
            )
            written_paths[skill.id].append(str(dest_md))
            for copied in _copy_skill_payload(skill.path.parent, dest_dir):
                written_paths[skill.id].append(str(copied))
    written = [{"id": skill_id, "paths": paths} for skill_id, paths in written_paths.items()]
    return written, removed


def render_header(vault_root: Path, project: str, stanza_ids: list[str]) -> str:
    git_ref = vault_git_ref(vault_root) or "none"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "<!--",
        "insitu-generated: true",
        f"vault: {vault_root}",
        f"git: {git_ref}",
        f"timestamp: {timestamp}",
        f"project: {project}",
        "stanzas:",
    ]
    if stanza_ids:
        lines.extend(f"- {sid}" for sid in stanza_ids)
    else:
        lines.append("-")
    lines.append("-->")
    return "\n".join(lines)


def _write_text_bounded(path: Path, text: str, *, timeout: float) -> str | None:
    """Write text. None on success. Error code if the write fails or does not finish."""
    error: list[str] = []

    def worker() -> None:
        try:
            path.write_text(text, encoding="utf-8")
        except OSError:
            error.append("adapter_write_failed")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return "adapter_locked"
    if error:
        return error[0]
    return None


def _read_surfaces(vault_root: Path) -> tuple[list[str] | None, dict | None]:
    path = vault_root / "config" / "surfaces.yaml"
    if not path.is_file():
        return None, None
    data = read_yaml(path)
    if not isinstance(data, dict):
        data = {}
    names = list(data.get("surfaces") or [])
    return [str(name) for name in names], None


def _render_protocol(vault_root: Path, resolved: dict) -> str:
    header = render_header(
        vault_root,
        resolved["project"],
        [item["id"] for item in resolved["core"]],
    )
    bodies = [item["content"] for item in resolved["core"]]
    text = header
    if bodies:
        text += "\n\n" + "\n\n".join(bodies)
    return text + "\n"


def _render_cursor_adapter(project: str, protocol_text: str) -> str:
    return (
        "---\n"
        "alwaysApply: true\n"
        f"description: Insitu composed protocol for {project}\n"
        "---\n\n"
        f"{protocol_text}"
    )


def materialize(
    vault_or_root: Vault | Path | str,
    working_folder: str | Path,
    project: str | None = None,
) -> dict:
    vault = _as_vault(vault_or_root)
    work = Path(working_folder)
    work.mkdir(parents=True, exist_ok=True)

    raw_key = project if project is not None else work.name
    try:
        key = validate_project_key(raw_key)
    except InvalidIdentity as exc:
        return {
            "ok": False,
            "error": "invalid_identity",
            "value": raw_key,
            "reason": str(exc),
        }

    resolved = resolve_protocol(vault, key)
    if not resolved["ok"]:
        return resolved

    surfaces, _err = _read_surfaces(vault.root)
    warnings: list[str] = []
    if surfaces is None:
        warnings.append("no_surfaces_configured")
        if resolved.get("skills"):
            warnings.append("skills_need_surfaces")
        surfaces = []
    else:
        for name in surfaces:
            if name not in KNOWN_SURFACES:
                return {"ok": False, "error": "unknown_surface", "surface": name}

    protocol_text = _render_protocol(vault.root, resolved)
    protocol_path = work / "PROTOCOL.md"
    protocol_path.write_text(protocol_text, encoding="utf-8")

    adapters: list[dict] = []
    for name in surfaces:
        dest = work / KNOWN_SURFACES[name]
        if dest.name in CONSTITUTION_NAMES:
            return {
                "ok": False,
                "error": "constitution_guard",
                "path": str(dest),
            }
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = (
            _render_cursor_adapter(key, protocol_text)
            if name == "cursor"
            else protocol_text
        )
        write_error = _write_text_bounded(
            dest, body, timeout=ADAPTER_WRITE_TIMEOUT_SECONDS
        )
        if write_error:
            warnings.append(write_error)
            continue
        adapters.append({"surface": name, "path": str(dest)})

    composed = iter_composed_skills(vault, vault.projects[key])
    if isinstance(composed, dict):
        return composed
    skills_written: list[dict] = []
    skills_removed: list[dict] = []
    if surfaces:
        skills_written, skills_removed = _write_mapped_skills(
            vault, work, key, surfaces, composed
        )

    result: dict = {
        "ok": True,
        "project": key,
        "protocol_path": str(protocol_path),
        "adapters": adapters,
        "skills": skills_written,
        "skills_removed": skills_removed,
        "warnings": warnings,
    }
    if "no_surfaces_configured" in warnings:
        detected = [
            name
            for name in (".grok", ".claude", ".cursor")
            if (work / name).is_dir()
        ]
        if detected:
            result["detected_host_dirs"] = detected
    return result
