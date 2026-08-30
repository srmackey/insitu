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


def chair_key(working_folder: str | Path) -> str:
    """The calling chair is the basename of the folder the session sits in."""
    return Path(str(working_folder).strip()).name.strip().casefold()


def check_map_write(
    root: str | Path,
    *,
    project: str,
    working_folder: str | Path,
) -> tuple[dict | None, str | None]:
    """Gate a mutating map write.

    Returns (refusal, warning). A refusal of None means the write may
    proceed. A warning rides a successful result rather than blocking it.
    """
    folder = str(working_folder or "").strip()
    if not folder:
        return (
            {
                "ok": False,
                "error": "working_folder_required",
                "detail": (
                    "mutating map tools need the folder this session sits in, "
                    "so the vault can tell which chair is asking"
                ),
            },
            None,
        )

    config = load_operators(root)
    if not config.initialized:
        # Pre-init. Behave as the server did before classes existed, and say
        # so. Failing closed here would lock every chair out of a vault with
        # no admin registered to unlock it.
        return None, PRE_INIT_WARNING

    chair = chair_key(folder)
    if config.is_admin(chair):
        return None, None

    target = _norm(project)
    if chair == target:
        return None, None

    return (
        {
            "ok": False,
            "error": "chair_bound",
            "chair": chair,
            "project": target,
            "working_folder": folder,
            "detail": (
                f"chair {chair!r} is bound to its own map and cannot write "
                f"{target!r}. An admin chair may name another project key."
            ),
        },
        None,
    )


def check_vault_write(
    root: str | Path,
    *,
    working_folder: str | Path,
    used_by: list[str],
    kind: str,
    object_id: str,
) -> tuple[dict | None, str | None]:
    """Gate a write to a shared vault object: a stanza, a role, or a skill.

    Authoring is open to every chair. What is gated is reach: a write that
    changes what a map other than this chair's composes is composition
    authority, and that is admin. So creating is always allowed, editing an
    object only this chair carries is allowed, and editing one that four
    other maps compose is not.

    `used_by` is the set of maps that compose the object today. Returns
    (refusal, warning), matching check_map_write.
    """
    folder = str(working_folder or "").strip()
    if not folder:
        return (
            {
                "ok": False,
                "error": "working_folder_required",
                "detail": (
                    "vault writes need the folder this session sits in, so the "
                    "vault can tell which chair is asking"
                ),
            },
            None,
        )

    config = load_operators(root)
    if not config.initialized:
        return None, PRE_INIT_WARNING

    chair = chair_key(folder)
    if config.is_admin(chair):
        return None, None

    others = sorted({_norm(key) for key in used_by} - {chair})
    if not others:
        return None, None

    return (
        {
            "ok": False,
            "error": "shared_object",
            "chair": chair,
            "kind": kind,
            "id": object_id,
            "used_by": others,
            "working_folder": folder,
            "detail": (
                f"chair {chair!r} is bound, and this {kind} is composed by "
                + ", ".join(repr(key) for key in others)
                + ". Changing it would change what those chairs compose, "
                "which is an admin action. Create your own instead, or ask "
                "an admin chair."
            ),
        },
        None,
    )


def check_grant(root: str | Path, *, working_folder: str | Path) -> dict | None:
    """Only an admin chair may change another map's class."""
    folder = str(working_folder or "").strip()
    if not folder:
        return {"ok": False, "error": "working_folder_required"}
    config = load_operators(root)
    if not config.initialized:
        return {
            "ok": False,
            "error": "not_initialized",
            "detail": PRE_INIT_WARNING,
        }
    chair = chair_key(folder)
    if config.is_admin(chair):
        return None
    return {
        "ok": False,
        "error": "admin_required",
        "chair": chair,
        "detail": f"chair {chair!r} is not admin; grant and revoke are admin only",
    }


def grant(
    root: str | Path,
    *,
    project: str,
    operator_class: str,
    working_folder: str | Path,
) -> dict:
    """Set a project's class. Admin only."""
    refusal = check_grant(root, working_folder=working_folder)
    if refusal is not None:
        return refusal
    key = _norm(project)
    if not key:
        return {"ok": False, "error": "empty_key", "detail": "project key is required"}
    klass = str(operator_class or "").strip().casefold()
    if klass not in KNOWN_CLASSES:
        return {
            "ok": False,
            "error": "unknown_class",
            "value": operator_class,
            "known": list(KNOWN_CLASSES),
        }
    config = load_operators(root)
    config.projects[key] = klass
    write_operators(root, config)
    return {"ok": True, "project": key, "class": klass, "admins": config.admins}


def revoke(
    root: str | Path,
    *,
    project: str,
    working_folder: str | Path,
) -> dict:
    """Drop a project back to the default class. Admin only.

    The last admin cannot revoke itself: that would leave a vault nobody can
    reconfigure, and `init` refuses once any admin exists.
    """
    refusal = check_grant(root, working_folder=working_folder)
    if refusal is not None:
        return refusal
    key = _norm(project)
    config = load_operators(root)
    if key not in config.projects:
        return {"ok": False, "error": "not_listed", "project": key}
    if config.projects[key] == CLASS_ADMIN and config.admins == [key]:
        return {
            "ok": False,
            "error": "last_admin",
            "project": key,
            "detail": (
                "revoking the only admin would leave the vault unreconfigurable, "
                "and init refuses once an admin exists. Grant another admin first."
            ),
        }
    config.projects.pop(key)
    write_operators(root, config)
    return {
        "ok": True,
        "project": key,
        "class": config.default_class,
        "admins": config.admins,
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
