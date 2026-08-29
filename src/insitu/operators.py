"""Operator classes: which chairs may mutate which maps.

Two classes, `admin` and `bound`. `bound` is the default and names chair
binding, not a rank: that chair may only touch its own map, in its own
folder. `admin` may name other project keys and other working folders,
and is the only class that may grant or revoke.

The store is `config/operators.yaml` in the vault, alongside
`pack-repos.yaml` and `surfaces.yaml`. Vault state, not install-folder
state, because INSITU_HOME moves and the code checkout is shared.

A vault with no config file is pre-init. It behaves as the server did
before this module existed, and says so. Failing closed instead would
lock every chair out of a vault that has no admin registered to unlock
it. Registering the first admin is `insitu init --admin <key>`, a
command-line step, deliberately not an MCP tool: an agent cannot claim
admin mid-session.

This is a discipline gate against casual cross-map writes, not a
security boundary. The file is hand-editable by anything with a shell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from insitu.store import read_yaml

CLASS_ADMIN = "admin"
CLASS_BOUND = "bound"
KNOWN_CLASSES = (CLASS_ADMIN, CLASS_BOUND)

PRE_INIT_WARNING = (
    "vault has no config/operators.yaml: running pre-init, every chair is "
    "unrestricted. Register an admin with `insitu init --admin <project-key>`."
)


@dataclass
class OperatorConfig:
    """Loaded operator config. `initialized` is False when the file is absent."""

    path: Path
    initialized: bool
    default_class: str = CLASS_BOUND
    projects: dict[str, str] = field(default_factory=dict)

    @property
    def admins(self) -> list[str]:
        return sorted(k for k, v in self.projects.items() if v == CLASS_ADMIN)

    def class_for(self, project: str) -> str:
        """Class of a project key. Unlisted keys take the default class."""
        return self.projects.get(_norm(project), self.default_class)

    def is_admin(self, project: str) -> bool:
        return self.class_for(project) == CLASS_ADMIN

    def to_yaml_data(self) -> dict[str, Any]:
        return {
            "default_class": self.default_class,
            "projects": {k: self.projects[k] for k in sorted(self.projects)},
        }


def _norm(project: str) -> str:
    return str(project or "").strip().casefold()


def config_path(root: str | Path) -> Path:
    return Path(root).resolve() / "config" / "operators.yaml"


def load_operators(root: str | Path) -> OperatorConfig:
    """Read config/operators.yaml. A missing file is pre-init, not an error."""
    path = config_path(root)
    if not path.is_file():
        return OperatorConfig(path=path, initialized=False)

    data = read_yaml(path)
    if not isinstance(data, dict):
        return OperatorConfig(path=path, initialized=True)

    default_class = str(data.get("default_class") or CLASS_BOUND).strip().casefold()
    if default_class not in KNOWN_CLASSES:
        default_class = CLASS_BOUND

    projects: dict[str, str] = {}
    rows = data.get("projects") or {}
    if isinstance(rows, dict):
        for key, value in rows.items():
            name = _norm(key)
            klass = str(value or "").strip().casefold()
            if not name or klass not in KNOWN_CLASSES:
                continue
            projects[name] = klass

    return OperatorConfig(
        path=path,
        initialized=True,
        default_class=default_class,
        projects=projects,
    )


def write_operators(root: str | Path, config: OperatorConfig) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(config.to_yaml_data(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def init_admin(root: str | Path, project: str) -> dict:
    """Register the first admin. Refuses once any admin exists."""
    key = _norm(project)
    if not key:
        return {
            "ok": False,
            "error": "empty_key",
            "detail": "project key is required",
        }

    config = load_operators(root)
    if config.admins:
        return {
            "ok": False,
            "error": "already_initialized",
            "detail": (
                "vault already has an admin: "
                + ", ".join(config.admins)
                + ". Use grant/revoke from an admin chair to change it."
            ),
            "admins": config.admins,
            "path": str(config.path),
        }

    config.initialized = True
    config.projects[key] = CLASS_ADMIN
    path = write_operators(root, config)
    return {
        "ok": True,
        "project": key,
        "class": CLASS_ADMIN,
        "default_class": config.default_class,
        "path": str(path),
    }


def operator_status(root: str | Path) -> dict:
    """Read-only view of the operator config, for the CLI and for callers."""
    config = load_operators(root)
    payload: dict[str, Any] = {
        "ok": True,
        "initialized": config.initialized,
        "default_class": config.default_class,
        "admins": config.admins,
        "projects": {k: config.projects[k] for k in sorted(config.projects)},
        "path": str(config.path),
    }
    if not config.initialized:
        payload["warning"] = PRE_INIT_WARNING
    return payload
