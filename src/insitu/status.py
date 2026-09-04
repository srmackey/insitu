"""Folder inspect card (DESIGN.md §9). Inspect only. No article bodies."""

from __future__ import annotations

from pathlib import Path

from insitu.identity import GLOBAL_PROJECT, InvalidIdentity, validate_project_key
from insitu.materialize import KNOWN_SURFACES, _read_surfaces, parse_header
from insitu.models import Vault
from insitu.resolve import attributed_core_sources, resolve_protocol
from insitu.store import load_vault


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


def _fmt_list(ids: list[str]) -> str:
    return ", ".join(ids) if ids else "none"


def _fmt_size(size: dict) -> str:
    n = size.get("article_count", 0)
    raw_bytes = int(size.get("bytes") or 0)
    tokens = int(size.get("estimated_tokens") or 0)
    if raw_bytes >= 1024:
        weight = f"~{raw_bytes / 1024:.1f} KB"
    else:
        weight = f"~{raw_bytes} bytes"
    if tokens >= 1000:
        tok = f"~{tokens / 1000:.1f}k tokens"
    else:
        tok = f"~{tokens} tokens"
    label = "article" if n == 1 else "articles"
    return f"{n} {label}, {weight}, {tok}"


def _source_label(row: dict) -> str:
    kind = row["kind"]
    if kind == "_global":
        return "_global"
    if kind == "role":
        return f"role {row['id']}"
    if kind == "import":
        return f"import {row['pack']}@{row['version']}"
    return "project"


def _render_card(result: dict) -> str:
    name = result.get("name")
    title = result["project"]
    if name:
        title = f"{title} ({name})"
    disk = result["disk"]
    if disk["current"]:
        state = "Mapped, composed, and materialized."
    elif disk["protocol"]["present"]:
        state = "Mapped and composed. Pack on disk is stale."
    else:
        state = "Mapped and composed. Not materialized."
    lines = [
        f"This folder is Insitu project {title}. {state}",
        "",
        "Map",
    ]
    roles = result["roles"]
    lines.append(f"- Role: {_fmt_list(roles)}")
    classes = result.get("classes") or []
    # A card that shows only the map would be describing a protocol this chair
    # does not have, whenever a class imposes or forbids anything.
    if classes:
        lines.append(f"- Class: {_fmt_list(classes)}")
    for row in result.get("imposed") or []:
        lines.append(
            f"- Imposed by {row['imposed_by']}: {row['id']} ({row['list']})"
        )
    for row in result.get("excluded") or []:
        lines.append(
            f"- Forbidden by {row['prohibited_by']}: {row['id']} (dropped from {row['list']})"
        )
    lines.append(
        "- _global included"
        if result["include_global"]
        else "- _global omitted"
    )
    lines.append(f"- Project-local core: {_fmt_list(result['core'])}")
    lines.append(f"- On-demand: {_fmt_list(result['on_demand'])}")
    imports = result["imports"]
    if imports:
        labels = [f"{item['pack']}@{item['version']}" for item in imports]
        lines.append(f"- Imports: {', '.join(labels)}")
    else:
        lines.append("- Imports: none")
    lines.append(f"- Repo: {result['repo'] or 'none'}")
    lines.append(f"- Notes: {'present' if result['notes'] else 'none'}")
    lines.append("")
    lines.append(f"Composed core: {_fmt_size(result['size'])}")
    lines.append("")
    if result["sources"]:
        lines.append("| Source | Articles |")
        lines.append("| ------ | ------- |")
        for row in result["sources"]:
            lines.append(f"| {_source_label(row)} | {_fmt_list(row['articles'])} |")
        lines.append("")
    proto = disk["protocol"]
    n = result["size"].get("article_count", 0)
    if not proto["present"]:
        lines.append("On disk: PROTOCOL.md is missing. Not materialized.")
    elif proto.get("unparseable"):
        lines.append(
            "On disk: PROTOCOL.md is present but the header is unparseable. Pack is stale."
        )
    elif disk["current"]:
        ts = proto.get("timestamp") or "unknown"
        adapter_dirs = sorted(
            {
                Path(row["path"]).parent.as_posix() + "/"
                for row in disk["adapters"]
                if row["present"]
            }
        )
        adapter_bit = (
            f" Host adapters are under {', '.join(adapter_dirs)}."
            if adapter_dirs
            else ""
        )
        missing = [row for row in disk["adapters"] if not row["present"]]
        missing_bit = ""
        if missing:
            bits = [
                f"{row['surface']} (`{Path(row['path']).as_posix()}`)"
                for row in missing
            ]
            missing_bit = f" Host adapters missing: {', '.join(bits)}."
        current_bit = " Pack looks current." if not missing else ""
        lines.append(
            f"On disk: PROTOCOL.md is generated ({ts}) and matches that "
            f"{n}-article list.{adapter_bit}{missing_bit}{current_bit}"
        )
    else:
        ts = proto.get("timestamp") or "unknown"
        lines.append(
            f"On disk: PROTOCOL.md is generated ({ts}) but the header article "
            "list does not match live compose. Pack is stale."
        )
    return "\n".join(lines) + "\n"


def project_status(
    vault_or_root: Vault | Path | str,
    working_folder: str | Path,
    project: str | None = None,
) -> dict:
    work = Path(working_folder)
    if not work.exists():
        return {
            "ok": False,
            "error": "working_folder_missing",
            "path": str(work),
        }
    if not work.is_dir():
        return {
            "ok": False,
            "error": "working_folder_not_directory",
            "path": str(work),
        }

    vault = _as_vault(vault_or_root)
    raw_key = project if project is not None else work.name
    try:
        key = validate_project_key(raw_key)
    except InvalidIdentity as exc:
        return _identity_error(raw_key, exc)

    resolved = resolve_protocol(vault, key)
    if not resolved["ok"]:
        return resolved

    vault = load_vault(vault.root)
    proj = vault.projects[key]
    sources = attributed_core_sources(vault, proj)
    if isinstance(sources, dict):
        return sources

    live_ids: list[str] = []
    for row in sources:
        live_ids.extend(row["articles"])

    protocol_path = work / "PROTOCOL.md"
    protocol: dict = {
        "path": str(protocol_path),
        "present": protocol_path.is_file(),
        "timestamp": None,
        "project": None,
        "articles": [],
        "matches": False,
    }
    if protocol["present"]:
        header = parse_header(protocol_path.read_text(encoding="utf-8"))
        if header is None:
            protocol["unparseable"] = True
        else:
            protocol["timestamp"] = header.get("timestamp")
            protocol["project"] = header.get("project")
            protocol["articles"] = list(header.get("articles") or [])
            protocol["matches"] = (
                protocol["project"] == key and protocol["articles"] == live_ids
            )

    surfaces, _err = _read_surfaces(vault.root)
    adapters: list[dict] = []
    if surfaces:
        for name in surfaces:
            rel = KNOWN_SURFACES.get(name)
            if rel is None:
                continue
            dest = work / rel
            adapters.append(
                {
                    "surface": name,
                    "path": rel.as_posix(),
                    "present": dest.is_file(),
                }
            )

    result = {
        "ok": True,
        "project": key,
        "name": proj.name,
        "repo": proj.repo,
        "roles": list(proj.roles),
        "classes": resolved.get("classes", []),
        "imposed": resolved.get("imposed", []),
        "excluded": resolved.get("excluded", []),
        "include_global": False
        if key == GLOBAL_PROJECT
        else proj.include_global,
        "core": list(proj.core),
        "on_demand": [item["id"] for item in resolved["on_demand"]],
        "imports": [item.as_dict() for item in proj.imports],
        "notes": bool(proj.notes and str(proj.notes).strip()),
        "size": resolved["size"],
        "sources": sources,
        "disk": {
            "protocol": protocol,
            "adapters": adapters,
            "current": bool(protocol["present"] and protocol["matches"]),
        },
    }
    result["card"] = _render_card(result)
    return result
