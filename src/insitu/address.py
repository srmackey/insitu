"""Resolve a chair address against nexus.md.

The folder tree is the hierarchy. nexus.md at the install root names the top
nexus and its nodes. A node of kind nexus has its own nexus.md. An address is
the nexus's own name, or that name, a slash, and a node's name. A nested
nexus is addressed by its own name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NodeRow:
    name: str
    path: str
    kind: str
    status: str
    sensitive: bool
    services: tuple[str, ...]
    triggers: str


@dataclass(frozen=True)
class Nexus:
    name: str
    folder: Path
    parent: str | None
    sensitive: bool
    nodes: tuple[NodeRow, ...]


@dataclass(frozen=True)
class Tree:
    root: Path
    top: Nexus
    nexuses: dict[str, Nexus]


@dataclass(frozen=True)
class Located:
    address: str
    slug: str
    nexus_dir: Path
    project_dir: Path
    is_nexus: bool
    is_root: bool
    sensitive: bool


def registry_root() -> Path | None:
    """Install root from INSITU_ROOT, when that folder has a nexus.md."""
    raw = os.environ.get("INSITU_ROOT", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not (path / "nexus.md").is_file():
        return None
    return path.resolve()


def is_within(root: Path, folder: Path) -> bool:
    try:
        Path(folder).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def read_nexus(folder: Path) -> Nexus | None:
    path = Path(folder) / "nexus.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    name = None
    parent = None
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if name is None and lowered.startswith("# nexus:"):
            name = stripped.split(":", 1)[1].strip()
        elif lowered.startswith("parent:"):
            parent = stripped.split(":", 1)[1].strip() or None
    if not name:
        return None
    return Nexus(
        name=name,
        folder=Path(folder),
        parent=parent,
        sensitive=False,
        nodes=tuple(_nodes(text)),
    )


def load_tree(root: Path) -> Tree | None:
    top = read_nexus(Path(root))
    if top is None:
        return None
    nexuses: dict[str, Nexus] = {}
    stack = [top]
    while stack:
        current = stack.pop()
        key = current.name.casefold()
        if key in nexuses:
            continue
        nexuses[key] = current
        for node in current.nodes:
            if node.kind != "nexus":
                continue
            child = read_nexus(_join(current.folder, node.path))
            if child is None:
                continue
            stack.append(
                Nexus(
                    name=child.name,
                    folder=child.folder,
                    parent=current.name,
                    sensitive=node.sensitive,
                    nodes=child.nodes,
                )
            )
    return Tree(root=Path(root).resolve(), top=nexuses[top.name.casefold()], nexuses=nexuses)


def resolve(tree: Tree, address: str, *, root_alias: bool = False) -> Located | None:
    parts = _split_address(address)
    if parts is None:
        return None
    if len(parts) == 1 and root_alias and parts[0].casefold() == "nexus":
        return _nexus_self(tree, tree.top)
    if len(parts) == 1:
        nexus = tree.nexuses.get(parts[0].casefold())
        if nexus is not None:
            return _nexus_self(tree, nexus)
        found = _unique_node(tree, parts[0])
        if found is None:
            return None
        return _node_loc(tree, *found)
    nexus = tree.nexuses.get(parts[0].casefold())
    if nexus is None:
        return None
    for row in nexus.nodes:
        if row.kind == "nexus":
            continue
        if row.name.casefold() == parts[1].casefold():
            return _node_loc(tree, nexus, row)
    return None


def derive_key(root: Path, folder: Path) -> str | None:
    """The address of a folder that is a nexus or a node in the tree."""
    tree = load_tree(root)
    if tree is None:
        return None
    folder = Path(folder).resolve()
    for nexus in tree.nexuses.values():
        if nexus.folder.resolve() == folder:
            return nexus.name.casefold()
    for nexus in tree.nexuses.values():
        for node in nexus.nodes:
            if node.kind == "nexus":
                continue
            if _join(nexus.folder, node.path).resolve() == folder:
                return f"{nexus.name.casefold()}/{node.name.casefold()}"
    return None


def bare_alias_map(root: Path, keys: set[str]) -> dict[str, str]:
    """Map a unique node basename to its address, when that address is stored."""
    tree = load_tree(root)
    if tree is None:
        return {}
    owners: dict[str, list[str]] = {}
    for nexus in tree.nexuses.values():
        for node in nexus.nodes:
            if node.kind == "nexus":
                continue
            address = f"{nexus.name.casefold()}/{node.name.casefold()}"
            if address not in keys:
                continue
            owners.setdefault(node.name.casefold(), []).append(address)
    return {
        bare: found[0]
        for bare, found in owners.items()
        if len(found) == 1 and bare not in keys
    }


def _nexus_self(tree: Tree, nexus: Nexus) -> Located:
    return Located(
        address=nexus.name.casefold(),
        slug=nexus.folder.name,
        nexus_dir=nexus.folder,
        project_dir=nexus.folder,
        is_nexus=True,
        is_root=nexus.folder.resolve() == tree.root.resolve(),
        sensitive=nexus.sensitive,
    )


def _node_loc(tree: Tree, nexus: Nexus, node: NodeRow) -> Located:
    project = _join(nexus.folder, node.path)
    return Located(
        address=f"{nexus.name.casefold()}/{node.name.casefold()}",
        slug=project.name,
        nexus_dir=nexus.folder,
        project_dir=project,
        is_nexus=False,
        is_root=False,
        sensitive=node.sensitive or nexus.sensitive,
    )


def _unique_node(tree: Tree, name: str) -> tuple[Nexus, NodeRow] | None:
    matches: list[tuple[Nexus, NodeRow]] = []
    for nexus in tree.nexuses.values():
        for row in nexus.nodes:
            if row.kind == "nexus":
                continue
            if row.name.casefold() == name.casefold():
                matches.append((nexus, row))
    if len(matches) == 1:
        return matches[0]
    return None


def _split_address(address: str) -> list[str] | None:
    text = address.strip().replace("\\", "/")
    if not text or text.startswith("/") or text.startswith("~"):
        return None
    if len(text) > 1 and text[1] == ":":
        return None
    parts = text.split("/")
    if len(parts) > 2 or any(part in {"", ".", ".."} for part in parts):
        return None
    return parts


def _join(folder: Path, rel: str) -> Path:
    raw = rel.strip().replace("\\", "/").strip("/")
    if not raw or any(part in {"", ".", ".."} for part in raw.split("/")):
        return folder / "__invalid__"
    return folder.joinpath(*raw.split("/"))


def _cells(line: str) -> list[str]:
    raw = line.strip()
    if not raw.startswith("|"):
        return []
    return [part.strip() for part in raw.strip("|").split("|")]


def _nodes(text: str) -> list[NodeRow]:
    lines = text.splitlines()
    header_at = None
    header: list[str] = []
    for index, line in enumerate(lines):
        cells = _cells(line)
        folded = [cell.casefold() for cell in cells]
        if cells and folded[0] == "node" and "path" in folded:
            header_at = index
            header = folded
            break
    if header_at is None:
        return []

    def column(*names: str) -> int | None:
        for name in names:
            if name in header:
                return header.index(name)
        return None

    i_name = column("node")
    i_path = column("path")
    i_kind = column("kind")
    i_status = column("status")
    i_sensitive = column("sensitive")
    i_services = column("services")
    i_triggers = column("triggers")
    rows: list[NodeRow] = []
    for line in lines[header_at + 1 :]:
        cells = _cells(line)
        if not cells:
            if rows:
                break
            continue
        if all(cell and set(cell) <= set("-: ") for cell in cells):
            continue

        def take(idx: int | None) -> str:
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx]

        node_name = take(i_name)
        if not node_name:
            continue
        services = tuple(
            part.strip()
            for part in take(i_services).split(",")
            if part.strip() and part.strip().casefold() != "none"
        )
        rows.append(
            NodeRow(
                name=node_name,
                path=take(i_path),
                kind=(take(i_kind) or "node").casefold(),
                status=(take(i_status) or "active").casefold(),
                sensitive=take(i_sensitive).casefold() in {"yes", "true"},
                services=services,
                triggers=take(i_triggers),
            )
        )
    return rows
