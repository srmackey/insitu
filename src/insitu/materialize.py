"""Write PROTOCOL.md and host adapters (DESIGN.md §10)."""

from __future__ import annotations

import shutil
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
ADAPTER_WRITE_TIMEOUT_SECONDS = 8


def _as_vault(vault_or_root: Vault | Path | str) -> Vault:
    if isinstance(vault_or_root, Vault):
        return vault_or_root
    return load_vault(vault_or_root)


def parse_header(text: str) -> dict | None:
    """Parse a materialize generated-file header. None if missing or unparseable."""
    start = text.find("<!--")
    end = text.find("-->")
    if start < 0 or end < 0 or end <= start:
        return None
    block = text[start + 4 : end]
    if "insitu-generated:" not in block:
        return None
    data: dict = {"articles": []}
    in_articles = False
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_articles:
            if line == "-":
                continue
            if line.startswith("- "):
                data["articles"].append(line[2:].strip())
                continue
            in_articles = False
        if line.startswith("articles:"):
            in_articles = True
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
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return "\n".join(
        [
            "<!--",
            "insitu-generated: true",
            f"vault: {vault_root}",
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


def render_header(
    vault_root: Path,
    project: str,
    article_ids: list[str],
    classes: list[str] | None = None,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "<!--",
        "insitu-generated: true",
        f"vault: {vault_root}",
        f"timestamp: {timestamp}",
        f"project: {project}",
    ]
    # The article list alone no longer explains this file: with obligations in
    # play, two chairs on the same map.yaml can compose differently. The classes
    # are what account for the difference, so they belong in the same header.
    if classes:
        lines.append(f"classes: {', '.join(classes)}")
    lines.append("articles:")
    if article_ids:
        lines.extend(f"- {sid}" for sid in article_ids)
    else:
        lines.append("-")
    lines.append("-->")
    return "\n".join(lines)


def render_on_demand(items: list[dict]) -> str:
    """The menu of what this chair may pull but is not carrying.

    DESIGN 9 has always said the resolved protocol carries an index of the
    on-demand set so an agent knows what it can request. That index reached
    `resolve_protocol`'s result and stopped there, and a result is not what a
    session loads: the host loads the generated file. So the articles were
    stored, associated, and unreachable, because knowing when the work calls
    for one requires knowing the set exists, and nothing put it in front of
    anybody.

    Id, description and cost, and no bodies. The description is the trigger
    surface, the same way it is for a skill, and the estimate is what holding
    it would cost. That is the trade on-demand was supposed to buy.
    """
    if not items:
        return ""
    lines = [
        "# On demand",
        "",
        "Associated with this chair and deliberately not composed. Pull one with "
        "`get_article` when the work calls for it. The estimate is what holding "
        "it costs.",
        "",
    ]
    for item in items:
        tokens = item.get("estimated_tokens")
        description = str(item.get("description") or "").strip()
        entry = f"- `{item['id']}`"
        if tokens:
            entry += f" ({tokens} tokens)"
        if description:
            entry += f". {description}"
        lines.append(entry)
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
        resolved.get("classes"),
    )
    sections = [header]
    menu = render_on_demand(resolved.get("on_demand") or [])
    if menu:
        sections.append(menu)
    sections.extend(item["content"] for item in resolved["core"])
    return "\n\n".join(sections) + "\n"


def _render_cursor_adapter(project: str, protocol_text: str) -> str:
    return (
        "---\n"
        "alwaysApply: true\n"
        f"description: Insitu composed protocol for {project}\n"
        "---\n\n"
        f"{protocol_text}"
    )


def _folder_key(work: Path) -> str | None:
    """The project key this folder is the checkout for, or None if it is not one.

    Same normalization the key itself gets when no project is named, so the
    comparison is between two keys rather than a key and a raw basename.
    """
    try:
        return validate_project_key(work.name)
    except InvalidIdentity:
        return None


def materialize(
    vault_or_root: Vault | Path | str,
    working_folder: str | Path,
    project: str | None = None,
) -> dict:
    vault = _as_vault(vault_or_root)
    work = Path(working_folder)

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

    # A named project must be the project this folder belongs to. Everywhere
    # else working_folder identifies the caller; here it is the destination,
    # and the operator gate only compares the two for a bound chair. An admin
    # is waved past that check, so without this one an admin sweep can write
    # one project's protocol over another project's checkout, and the skill
    # prune below would delete the generated skills it found there. Project key
    # is defined as the folder basename, so a mismatch is an error for every
    # class, including a pre-init vault.
    if project is not None and _folder_key(work) != key:
        return {
            "ok": False,
            "error": "folder_project_mismatch",
            "project": key,
            "folder": work.name,
            "working_folder": str(work),
            "detail": (
                f"working folder {work.name!r} is not the checkout for {key!r}. "
                "materialize writes into the folder it is given, so that "
                "folder's basename must be the project key. A sweep names each "
                "project's own checkout."
            ),
        }

    work.mkdir(parents=True, exist_ok=True)

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
