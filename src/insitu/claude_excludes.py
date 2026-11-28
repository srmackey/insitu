"""Claude instruction excludes for a chair that has its own protocol.

`materialize` merges these into `.claude/settings.local.json`. The list names
each ancestor inside the install that has a `CLAUDE.md` shim or a
`.claude/rules` directory. It does not name this chair's own files. A map with
no role is still using an ancestor protocol, so it gets no list.

An excluded shim takes its `@AGENTS.md` import with it, so excluding ancestor
shims keeps ancestor constitutions out whether or not the start folder has
Claude's external-import approval.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SHIM = Path("CLAUDE.md")
RULES_DIR = Path(".claude") / "rules"
SETTINGS_REL = Path(".claude") / "settings.local.json"
EXCLUDE_KEY = "claudeMdExcludes"

# Per ancestor, in the order Claude loads them: the shim, then the rules.
_TARGETS = ((SHIM, "/CLAUDE.md", Path.is_file), (RULES_DIR, "/.claude/rules/**", Path.is_dir))


def _win_path(path: Path, kind: str) -> Path | None:
    """Another spelling of an existing path. None when the OS has no second form.

    This is a path query, not a process. The server still does not shell out.
    """
    if os.name != "nt":
        return None
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    call = (
        ctypes.windll.kernel32.GetShortPathNameW
        if kind == "short"
        else ctypes.windll.kernel32.GetLongPathNameW
    )
    written = call(str(path), buffer, len(buffer))
    if written == 0 or written > len(buffer):
        return None
    return Path(buffer.value)


def path_spellings(path: Path) -> list[Path]:
    """Spellings Claude may record for one directory. The resolved path is first.

    The second spelling is the 8.3 form of the user profile with the rest of
    the path left long. Shortening every later folder is a third string, and
    it is not the one a session stores when its profile prefix was already short.
    """
    resolved = path.resolve()
    found = [resolved]
    home = Path.home().resolve()
    short_home = _win_path(home, "short")
    if short_home is None or short_home == home:
        return found
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return found
    mixed = short_home / relative
    if mixed not in found:
        found.append(mixed)
    return found


def ancestor_targets(working_folder: Path, install_root: Path) -> list[tuple[Path, str]]:
    """Ancestors inside the install, farthest first, with the glob suffix of each
    instruction file they hold: a `CLAUDE.md` shim, then `.claude/rules`."""
    work = working_folder.resolve()
    root = install_root.resolve()
    chain: list[Path] = []
    current = work.parent
    while True:
        try:
            current.resolve().relative_to(root)
        except ValueError:
            break
        chain.append(current)
        if current.resolve() == root:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    chain.reverse()
    found: list[tuple[Path, str]] = []
    for ancestor in chain:
        for rel, suffix, exists in _TARGETS:
            if exists(ancestor / rel):
                found.append((ancestor, suffix))
    return found


def _glob_for(spelled_ancestor: Path, spelled_root: Path, suffix: str) -> str | None:
    try:
        spelled_ancestor.relative_to(spelled_root)
    except ValueError:
        return None
    container = spelled_root.parent
    try:
        relative = spelled_ancestor.relative_to(container.parent)
    except ValueError:
        relative = Path(container.name) / spelled_ancestor.relative_to(container)
    return "**/" + relative.as_posix() + suffix


def ancestor_globs(
    working_folder: Path,
    install_root: Path,
    spellings=path_spellings,
) -> list[str]:
    """Globs for ancestor shims and rule directories, one per path spelling.

    The glob starts at the folder that contains the install, so a nested
    checkout whose name matches the install root does not collide with it.
    """
    globs: list[str] = []
    root_spellings = spellings(install_root)
    for ancestor, suffix in ancestor_targets(working_folder, install_root):
        for spelled in spellings(ancestor):
            for spelled_root in root_spellings:
                glob = _glob_for(spelled, spelled_root, suffix)
                if glob is not None and glob not in globs:
                    globs.append(glob)
                    break
    return globs


def merge_excludes(working_folder: Path, globs: list[str]) -> tuple[Path | None, str | None]:
    """Set `claudeMdExcludes` and leave every other key. None path on refusal.

    The error code is `claude_excludes_invalid` when the file is not a JSON
    object. The file is not written in that case.
    """
    if not globs:
        return None, None
    path = working_folder / SETTINGS_REL
    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "claude_excludes_invalid"
        if not isinstance(loaded, dict):
            return None, "claude_excludes_invalid"
        data = loaded
    if data.get(EXCLUDE_KEY) == globs:
        return path, None
    data[EXCLUDE_KEY] = globs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path, None
