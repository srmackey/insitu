"""Review dial for vault mutations (DESIGN.md §11)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

from insitu.store import read_yaml

MODES = {"auto", "review"}
DEFAULT_MODE = "review"
GIT_TIMEOUT_SECONDS = 15


def load_review_policy(vault_root: Path) -> dict:
    path = Path(vault_root) / "config" / "review-policy.yaml"
    if not path.is_file():
        return {"ok": True, "default": DEFAULT_MODE}
    data = read_yaml(path)
    if not isinstance(data, dict):
        return {"ok": False, "error": "invalid_review_policy", "value": data}
    mode = data.get("default", DEFAULT_MODE)
    if mode not in MODES:
        return {"ok": False, "error": "invalid_review_policy", "value": mode}
    return {"ok": True, "default": mode}


def git_present(vault_root: Path) -> bool:
    return (Path(vault_root) / ".git").exists()


def apply_review(
    vault_root: Path,
    paths: Iterable[Path],
    message: str,
    *,
    policy: dict | None = None,
) -> dict:
    vault_root = Path(vault_root)
    loaded = policy if policy is not None else load_review_policy(vault_root)
    if not loaded.get("ok"):
        return loaded
    mode = loaded["default"]
    rels: list[str] = []
    root = vault_root.resolve()
    for path in paths:
        resolved = Path(path).resolve()
        rels.append(resolved.relative_to(root).as_posix())
    staged = False
    committed = False
    if rels and git_present(vault_root):
        try:
            added = subprocess.run(
                ["git", "add", "--", *rels],
                cwd=vault_root,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": "git_timeout",
                "review": mode,
                "op": "add",
                "staged": False,
            }
        if added.returncode != 0:
            return {
                "ok": False,
                "error": "git_add_failed",
                "review": mode,
                "stderr": added.stderr.strip(),
            }
        staged = True
        if mode == "auto":
            try:
                committed_run = subprocess.run(
                    ["git", "commit", "-m", message],
                    cwd=vault_root,
                    capture_output=True,
                    text=True,
                    timeout=GIT_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "error": "git_timeout",
                    "review": mode,
                    "op": "commit",
                    "staged": True,
                }
            if committed_run.returncode != 0:
                return {
                    "ok": False,
                    "error": "git_commit_failed",
                    "review": mode,
                    "staged": True,
                    "stderr": committed_run.stderr.strip(),
                }
            committed = True
    return {
        "ok": True,
        "review": mode,
        "staged": staged,
        "committed": committed,
    }
