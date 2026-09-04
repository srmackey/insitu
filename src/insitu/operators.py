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
#: The rights ladder, and it is deliberately two rungs. A chair holds a set of
#: classes and its rights are their union, which stays unambiguous only while
#: there is nothing to be ambiguous about. Keep this dumb.
RIGHTS_CLASSES = (CLASS_ADMIN, CLASS_BOUND)
KNOWN_CLASSES = RIGHTS_CLASSES

PRE_INIT_WARNING = (
    "vault has no config/operators.yaml: running pre-init, every chair is "
    "unrestricted. Register an admin with `insitu init --admin <project-key>`."
)


@dataclass
class ClassDef:
    """A named class: what it grants, what it imposes, what it forbids.

    `rights` is one rung of the two-level ladder. `obligations` are articles
    every chair in this class composes whether or not its map lists them.
    `prohibitions` are articles such a chair may not compose at all.
    """

    name: str
    rights: str = CLASS_BOUND
    core: list[str] = field(default_factory=list)
    on_demand: list[str] = field(default_factory=list)
    prohibitions: list[str] = field(default_factory=list)

    def imposes(self) -> bool:
        return bool(self.core or self.on_demand or self.prohibitions)

    def to_yaml_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.rights != CLASS_BOUND:
            data["rights"] = self.rights
        if self.core or self.on_demand:
            obligations: dict[str, Any] = {}
            if self.core:
                obligations["core"] = list(self.core)
            if self.on_demand:
                obligations["on_demand"] = list(self.on_demand)
            data["obligations"] = obligations
        if self.prohibitions:
            data["prohibitions"] = list(self.prohibitions)
        return data


@dataclass
class OperatorConfig:
    """Loaded operator config. `initialized` is False when the file is absent."""

    path: Path
    initialized: bool
    default_class: str = CLASS_BOUND
    projects: dict[str, list[str]] = field(default_factory=dict)
    classes: dict[str, ClassDef] = field(default_factory=dict)

    @property
    def admins(self) -> list[str]:
        return sorted(k for k in self.projects if self.is_admin(k))

    def classes_for(self, project: str) -> list[str]:
        """The set of classes a chair holds. Unlisted keys take the default."""
        held = self.projects.get(_norm(project))
        if not held:
            return [self.default_class]
        return list(held)

    def definition(self, class_name: str) -> ClassDef:
        """A class definition, synthesised for the two built-in rights classes."""
        name = _norm(class_name)
        found = self.classes.get(name)
        if found is not None:
            return found
        rights = CLASS_ADMIN if name == CLASS_ADMIN else CLASS_BOUND
        return ClassDef(name=name, rights=rights)

    def rights_for(self, project: str) -> str:
        """Rights are the union over the held set, on a two-rung ladder."""
        for name in self.classes_for(project):
            if self.definition(name).rights == CLASS_ADMIN:
                return CLASS_ADMIN
        return CLASS_BOUND

    def class_for(self, project: str) -> str:
        """The chair's rights rung. Kept for callers that want one word."""
        return self.rights_for(project)

    def is_admin(self, project: str) -> bool:
        return self.rights_for(project) == CLASS_ADMIN

    def obligations_for(self, project: str) -> tuple[list[str], list[str]]:
        """Articles this chair composes because of what it is, not what it chose.

        Ordered by the chair's own class list, so the order is something the
        operator can see and change rather than an artefact of dict iteration.
        """
        core: list[str] = []
        on_demand: list[str] = []
        for name in self.classes_for(project):
            definition = self.definition(name)
            for article_id in definition.core:
                if article_id not in core:
                    core.append(article_id)
            for article_id in definition.on_demand:
                if article_id not in on_demand:
                    on_demand.append(article_id)
        return core, on_demand

    def prohibitions_for(self, project: str) -> list[str]:
        """Articles this chair may not compose, whatever its map says."""
        out: list[str] = []
        for name in self.classes_for(project):
            for article_id in self.definition(name).prohibitions:
                if article_id not in out:
                    out.append(article_id)
        return out

    def imposing_class(self, project: str, article_id: str) -> str | None:
        """Which held class put this article on the chair, if any."""
        for name in self.classes_for(project):
            definition = self.definition(name)
            if article_id in definition.core or article_id in definition.on_demand:
                return name
        return None

    def prohibiting_class(self, project: str, article_id: str) -> str | None:
        for name in self.classes_for(project):
            if article_id in self.definition(name).prohibitions:
                return name
        return None

    def to_yaml_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"default_class": self.default_class}
        if self.classes:
            data["classes"] = {
                name: self.classes[name].to_yaml_data() for name in sorted(self.classes)
            }
        rows: dict[str, Any] = {}
        for key in sorted(self.projects):
            held = self.projects[key]
            # One class stays a bare string, which is what every existing file
            # holds and what most chairs will always need.
            rows[key] = held[0] if len(held) == 1 else list(held)
        data["projects"] = rows
        return data


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

    classes = _load_classes(data.get("classes"))

    default_class = str(data.get("default_class") or CLASS_BOUND).strip().casefold()
    if default_class not in RIGHTS_CLASSES and default_class not in classes:
        default_class = CLASS_BOUND

    known = set(RIGHTS_CLASSES) | set(classes)
    projects: dict[str, list[str]] = {}
    rows = data.get("projects") or {}
    if isinstance(rows, dict):
        for key, value in rows.items():
            name = _norm(key)
            if not name:
                continue
            # A bare string is one class. That is every file written before
            # classes became a set, and it stays the common shape.
            raw = [value] if isinstance(value, str) else list(value or [])
            held = [n for n in (_norm(item) for item in raw) if n in known]
            if held:
                projects[name] = list(dict.fromkeys(held))

    return OperatorConfig(
        path=path,
        initialized=True,
        default_class=default_class,
        projects=projects,
        classes=classes,
    )


def _load_classes(raw: Any) -> dict[str, ClassDef]:
    """Read the optional `classes:` block. A malformed entry is skipped, not fatal."""
    out: dict[str, ClassDef] = {}
    if not isinstance(raw, dict):
        return out
    for key, body in raw.items():
        name = _norm(key)
        if not name or name in RIGHTS_CLASSES:
            # `admin` and `bound` are the ladder itself. Letting a file
            # redefine them would make the rights union mean something
            # different per vault.
            continue
        body = body if isinstance(body, dict) else {}
        rights = str(body.get("rights") or CLASS_BOUND).strip().casefold()
        if rights not in RIGHTS_CLASSES:
            rights = CLASS_BOUND
        obligations = body.get("obligations")
        obligations = obligations if isinstance(obligations, dict) else {}
        out[name] = ClassDef(
            name=name,
            rights=rights,
            core=_id_list(obligations.get("core")),
            on_demand=_id_list(obligations.get("on_demand")),
            prohibitions=_id_list(body.get("prohibitions")),
        )
    return out


def _id_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


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
    config.projects[key] = [CLASS_ADMIN]
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
    """Gate a write to a shared vault object: an article, a role, or a skill.

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
    config = load_operators(root)
    known = set(RIGHTS_CLASSES) | set(config.classes)
    # A set replaces the set. Granting is stating what this chair is, not
    # appending to a list nobody can see in one place.
    raw = [operator_class] if isinstance(operator_class, str) else list(operator_class or [])
    held = [n for n in (_norm(item) for item in raw) if n]
    if not held:
        return {"ok": False, "error": "empty_class", "detail": "at least one class is required"}
    unknown = [name for name in held if name not in known]
    if unknown:
        return {
            "ok": False,
            "error": "unknown_class",
            "value": unknown,
            "known": sorted(known),
        }
    config.projects[key] = list(dict.fromkeys(held))
    write_operators(root, config)
    return {
        "ok": True,
        "project": key,
        "classes": config.projects[key],
        "class": config.rights_for(key),
        "admins": config.admins,
    }


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
    if config.is_admin(key) and config.admins == [key]:
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
        "projects": {
            key: {
                "classes": config.classes_for(key),
                "rights": config.rights_for(key),
            }
            for key in sorted(config.projects)
        },
        "classes": {
            name: config.classes[name].to_yaml_data() for name in sorted(config.classes)
        },
        "path": str(config.path),
    }
    if not config.initialized:
        payload["warning"] = PRE_INIT_WARNING
    return payload
