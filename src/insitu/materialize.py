"""Write PROTOCOL.md and host adapters (DESIGN.md §10)."""

from __future__ import annotations

import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from insitu.store import SKILL_PAYLOAD_DIRS, VaultReadError, read_yaml, skill_payload_paths

from insitu.address import derive_key, is_within, registry_root, resolve, load_tree
from insitu.identity import InvalidIdentity, validate_project_key
from insitu.models import Skill, Vault
from insitu.resolve import iter_composed_skills, resolve_protocol
from insitu.store import load_vault

# CLAUDE.md is never a write target. AGENTS.md is written only under
# stamp-or-missing, which is applied whenever that file is the destination.
NEVER_WRITE = frozenset({"CLAUDE.md", "CLAUDE.local.md"})
APPLY_FORMATS = frozenset({"markdown", "mdc"})
KNOWN_WRITES = frozenset({"stamp-or-missing"})
AGENTS_PLATFORM = "agents"
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
    roots: list[tuple[str, Path]],
    skills: list[Skill],
) -> tuple[list[dict], list[dict]]:
    written_paths: dict[str, list[str]] = {skill.id: [] for skill in skills}
    removed: list[dict] = []
    composed = {skill.id for skill in skills}
    for name, rel in roots:
        root = work / rel
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


class PlatformPlan:
    """What this call will write, and which enabled names it will not.

    ``source`` is ``platforms`` when ``platforms.yaml`` supplied ``enabled``,
    and ``default`` when that file is absent. An empty ``enabled`` list is a
    real list: no writes, and not the default.
    """

    def __init__(
        self,
        source: str,
        writes: list[tuple[str, Path, str, str | None]],
        skills: list[tuple[str, Path]],
        unapplied: list[dict],
    ) -> None:
        self.source = source
        self.writes = writes
        self.skills = skills
        self.unapplied = unapplied


def _platforms_invalid(path: Path) -> dict:
    return {
        "ok": False,
        "error": "platforms_invalid",
        "path": str(path),
        "detail": "platforms.yaml needs an enabled list of platform names.",
    }


def _agents_definition() -> dict:
    return {
        "instructions": [
            {
                "scope": "project",
                "path": "AGENTS.md",
                "format": "markdown",
                "write": "stamp-or-missing",
            }
        ]
    }


def carries_insitu_stamp(text: str) -> bool:
    """True when the file opens with an Insitu generated-file comment."""
    stripped = text.lstrip("\ufeff").lstrip()
    if not stripped.startswith("<!--"):
        return False
    end = stripped.find("-->")
    if end < 0:
        return False
    return "insitu-generated:" in stripped[:end]


def _project_rel(raw: object) -> tuple[Path | None, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "missing_path"
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return None, "path_escapes"
    return path, None


def _instruction_writes(
    platform: str, definition: dict
) -> tuple[list[tuple[str, Path, str, str | None]], list[dict]]:
    """Project instruction files this definition can apply, and the ones it cannot."""
    entries = definition.get("instructions") or []
    if not isinstance(entries, list):
        return [], [{"platform": platform, "reason": "instructions_not_a_list"}]
    writes: list[tuple[str, Path, str, str | None]] = []
    problems: list[dict] = []
    saw_project = False
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("scope") != "project":
            continue
        saw_project = True
        raw_path = entry.get("path")
        rel, err = _project_rel(raw_path)
        shown = rel.as_posix() if rel is not None else raw_path
        if err or rel is None:
            item: dict = {"platform": platform, "reason": err or "missing_path"}
            if isinstance(shown, str):
                item["path"] = shown
            problems.append(item)
            continue
        if rel.name in NEVER_WRITE:
            problems.append(
                {"platform": platform, "reason": "constitution", "path": rel.as_posix()}
            )
            continue
        fmt = entry.get("format")
        if not isinstance(fmt, str) or fmt not in APPLY_FORMATS:
            problems.append(
                {
                    "platform": platform,
                    "reason": "unknown_format",
                    "path": rel.as_posix(),
                }
            )
            continue
        mode = entry.get("write")
        if mode is not None and (not isinstance(mode, str) or mode not in KNOWN_WRITES):
            problems.append(
                {
                    "platform": platform,
                    "reason": "unknown_write",
                    "path": rel.as_posix(),
                }
            )
            continue
        if rel.name == "AGENTS.md":
            mode = "stamp-or-missing"
        writes.append((platform, rel, fmt, mode if isinstance(mode, str) else None))
    if not saw_project and not problems:
        problems.append({"platform": platform, "reason": "no_project_instruction"})
    return writes, problems


def _skill_roots(
    platform: str, definition: dict
) -> tuple[list[tuple[str, Path]], list[dict]]:
    entries = definition.get("skills") or []
    if not isinstance(entries, list):
        return [], [{"platform": platform, "reason": "skills_not_a_list"}]
    roots: list[tuple[str, Path]] = []
    problems: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("scope") != "project":
            continue
        raw_path = entry.get("path")
        rel, err = _project_rel(raw_path)
        if err or rel is None:
            item = {"platform": platform, "reason": err or "missing_path"}
            if isinstance(raw_path, str):
                item["path"] = raw_path
            problems.append(item)
            continue
        roots.append((platform, rel))
    return roots, problems


def _plan_definition(platform: str, definition: object) -> tuple[
    list[tuple[str, Path, str, str | None]],
    list[tuple[str, Path]],
    list[dict],
]:
    if not isinstance(definition, dict):
        return [], [], [{"platform": platform, "reason": "not_a_definition"}]
    writes, problems = _instruction_writes(platform, definition)
    if not writes:
        return [], [], problems
    roots, skill_problems = _skill_roots(platform, definition)
    return writes, roots, problems + skill_problems


def plan_platforms() -> tuple[PlatformPlan | None, dict | None]:
    """The apply plan for this process's install root.

    No environment file, and no ``INSITU_ROOT``, both mean the ``agents``
    default. A present file that is not a usable list is an error. The vault
    ``config/surfaces.yaml`` is not a list.
    """
    reg = registry_root()
    if reg is None:
        writes, roots, problems = _plan_definition(AGENTS_PLATFORM, _agents_definition())
        return PlatformPlan("default", writes, roots, problems), None
    path = reg / "platforms.yaml"
    if not path.is_file():
        writes, roots, problems = _plan_definition(AGENTS_PLATFORM, _agents_definition())
        return PlatformPlan("default", writes, roots, problems), None
    try:
        data = read_yaml(path)
    except VaultReadError:
        return None, _platforms_invalid(path)
    if not isinstance(data, dict) or not isinstance(data.get("enabled"), list):
        return None, _platforms_invalid(path)
    catalog = data.get("platforms")
    if catalog is None:
        catalog = {}
    if not isinstance(catalog, dict):
        return None, _platforms_invalid(path)
    names: list[str] = []
    for name in data["enabled"]:
        if not isinstance(name, str) or not name.strip():
            return None, _platforms_invalid(path)
        names.append(name)
    writes: list[tuple[str, Path, str, str | None]] = []
    roots: list[tuple[str, Path]] = []
    unapplied: list[dict] = []
    for name in names:
        if name not in catalog:
            unapplied.append({"platform": name, "reason": "no_definition"})
            continue
        got, skill_roots, problems = _plan_definition(name, catalog[name])
        writes.extend(got)
        roots.extend(skill_roots)
        unapplied.extend(problems)
    return PlatformPlan("platforms", writes, roots, unapplied), None


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

    reg = registry_root()
    inside = reg is not None and is_within(reg, work)
    if inside:
        derived = derive_key(reg, work)
        if derived is None:
            return {
                "ok": False,
                "error": "not_in_registry",
                "working_folder": str(work),
                "detail": (
                    "working folder is inside the install tree and is not a "
                    "chair in nexus.md. materialize will not guess a key from "
                    "the folder name."
                ),
            }
        if project is not None:
            try:
                named = validate_project_key(project)
            except InvalidIdentity as exc:
                return {
                    "ok": False,
                    "error": "invalid_identity",
                    "value": project,
                    "reason": str(exc),
                }
            tree = load_tree(reg)
            located = resolve(tree, named) if tree is not None else None
            named_address = located.address if located is not None else named
            if named_address != derived:
                return {
                    "ok": False,
                    "error": "folder_project_mismatch",
                    "project": named_address,
                    "folder": work.name,
                    "working_folder": str(work),
                    "detail": (
                        f"working folder {work.name!r} is the chair {derived!r} "
                        f"in nexus.md, not {named_address!r}."
                    ),
                }
        key = derived
    else:
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
        if "/" in key:
            return {
                "ok": False,
                "error": "registry_required",
                "project": key,
                "detail": (
                    "an address key is derived from nexus.md. Set INSITU_ROOT "
                    "to the install root that holds that file."
                ),
            }

        # A named project must be the project this folder belongs to. Everywhere
        # else working_folder identifies the caller; here it is the destination,
        # and the operator gate only compares the two for a bound chair. An admin
        # is waved past that check, so without this one an admin sweep can write
        # one project's protocol over another project's checkout, and the skill
        # prune below would delete the generated skills it found there. Outside
        # an install tree the project key is the folder basename, so a mismatch
        # is an error for every class, including a pre-init vault.
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

    if not work.exists():
        return {
            "ok": False,
            "error": "working_folder_missing",
            "path": str(work),
            "project": key,
            "detail": (
                f"working folder {str(work)!r} does not exist. "
                "materialize writes into an existing checkout; it does not "
                "create one. Stop and ask which folder this project lives in."
            ),
        }
    if not work.is_dir():
        return {
            "ok": False,
            "error": "working_folder_not_directory",
            "path": str(work),
            "project": key,
            "detail": (
                f"working folder {str(work)!r} is not a directory. "
                "Stop and ask which folder this project lives in."
            ),
        }

    resolved = resolve_protocol(vault, key)
    if not resolved["ok"]:
        return resolved

    plan, err = plan_platforms()
    if err is not None:
        return err
    assert plan is not None

    protocol_text = _render_protocol(vault.root, resolved)
    protocol_path = work / "PROTOCOL.md"
    protocol_path.write_text(protocol_text, encoding="utf-8")

    warnings: list[str] = []
    adapters: list[dict] = []
    unchanged: list[dict] = []
    for platform, rel, fmt, mode in plan.writes:
        dest = work / rel
        if mode == "stamp-or-missing" and dest.is_file():
            try:
                existing = dest.read_text(encoding="utf-8")
            except OSError:
                warnings.append("adapter_write_failed")
                continue
            if not carries_insitu_stamp(existing):
                unchanged.append(
                    {
                        "platform": platform,
                        "path": str(dest),
                        "reason": "unstamped",
                    }
                )
                continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = (
            _render_cursor_adapter(key, protocol_text)
            if fmt == "mdc"
            else protocol_text
        )
        write_error = _write_text_bounded(
            dest, body, timeout=ADAPTER_WRITE_TIMEOUT_SECONDS
        )
        if write_error:
            warnings.append(write_error)
            continue
        adapters.append({"surface": platform, "path": str(dest)})

    composed = iter_composed_skills(vault, vault.projects[key])
    if isinstance(composed, dict):
        return composed
    skills_written: list[dict] = []
    skills_removed: list[dict] = []
    if plan.skills:
        skills_written, skills_removed = _write_mapped_skills(
            vault, work, key, plan.skills, composed
        )
    elif (
        composed
        and plan.source == "platforms"
        and plan.writes
    ):
        warnings.append("skills_need_surfaces")

    result: dict = {
        "ok": True,
        "project": key,
        "protocol_path": str(protocol_path),
        "adapters": adapters,
        "skills": skills_written,
        "skills_removed": skills_removed,
        "warnings": warnings,
        "platform_source": plan.source,
        "unapplied": plan.unapplied,
    }
    if unchanged:
        result["unchanged"] = unchanged
    if plan.source == "default":
        result["platform"] = AGENTS_PLATFORM
    return result
