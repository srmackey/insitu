"""In-memory vault records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Article:
    id: str
    path: Path
    title: str
    description: str
    tags: list[str]
    content: str
    frontmatter_id: str | None


@dataclass
class Skill:
    id: str
    path: Path
    name: str
    description: str
    content: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    payload: list[str] = field(default_factory=list)


@dataclass
class Role:
    id: str
    path: Path
    name: str | None
    description: str | None
    core: list[str]
    on_demand: list[str]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportRecord:
    pack: str
    version: str
    articles: list[str] | None = None
    skills: list[str] | None = None
    on_demand: list[str] | None = None

    def is_capability(self) -> bool:
        return self.articles is None and self.skills is None and self.on_demand is None

    def article_members(self) -> list[str]:
        """Every article this record imports, whichever list it lands in."""
        return list(self.articles or []) + list(self.on_demand or [])

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"pack": self.pack, "version": self.version}
        if self.articles is not None:
            data["articles"] = list(self.articles)
        if self.on_demand is not None:
            data["on_demand"] = list(self.on_demand)
        if self.skills is not None:
            data["skills"] = list(self.skills)
        return data


@dataclass
class PackRepo:
    name: str
    path: Path


@dataclass
class PackVersion:
    pack_id: str
    version: str
    path: Path
    source: str | None
    articles: dict[str, Article]
    role: Role | None
    pack_yaml: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)


@dataclass
class Project:
    key: str
    path: Path
    repo: str | None
    name: str | None
    aka: list[str]
    core: list[str]
    on_demand: list[str]
    include_global: bool
    notes: str | None
    roles: list[str] = field(default_factory=list)
    imports: list[ImportRecord] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Vault:
    root: Path
    articles: dict[str, Article]
    projects: dict[str, Project]
    roles: dict[str, Role] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    pack_repos: list[PackRepo] = field(default_factory=list)
    library: dict[str, dict[str, PackVersion]] = field(default_factory=dict)
    lock: dict[str, Any] = field(default_factory=dict)
