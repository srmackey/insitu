# AGENTS.md — Insitu

Guidance for agents and contributors working in this repo.

**Product.** Insitu is a portable MCP server for **situated identity**: who you are *here*. It stores reusable **articles**, **roles**, project-mapped **skills**, and versioned **packs**, and composes a **project-specific protocol**. Complementary to ContextForge (system/dev context). Not a second brain.

**Design lock.** `DESIGN.md` is the locked spec (v0.16, 2026-09-03). Implement against it. Role and project authoring, user-gated delete, validate findings, the `provenance/` why-log tree, the on-demand rename, pack-install (0.9), `project_status` (0.10), skills (0.11), pack-skill install (0.12), operator classes plus the on-demand install grain (0.13), the removal of all git operations (0.14), and the article vocabulary with role membership held only in the role file (0.16) are in `src/`. Do not add surface it does not name (search, ACL, rename tools, nested roles, role-carried skills) without an explicit design change.

DESIGN is the current shape, not a settled demand. Best practices, first-principles thinking, optimization, and enabling the operator to iterate quickly should always be considered. Proposing defensible improvements is always in scope.

## Agent stance

You are a careful steward of a small, markdown-first MCP. Files on disk are the truth. Insitu runs no git and has no subprocess surface; keep it that way. Prefer the existing primitives (article, project map, `resolve_protocol`) before adding new ones.

## Stack

- Python 3.11+, `uv`, FastMCP, Pydantic v2
- Markdown + YAML frontmatter on disk; no required database in v1
- Tests with pytest under `tests/`
- `uv sync` / `uv run pytest` / `uv run insitu`

## Invariants

- A **protocol** is composed, never a catalog row. Session start is `resolve_protocol`.
- An **article** is one markdown file under the user's vault `articles/`. Why-logs live under `provenance/<id>.md` and are not articles. Leftover `*.prov.md` under `articles/` is also not an article.
- Project key = working folder basename = `projects/<folder>/`. Missing project is a structured miss, not a catalog scan.
- Vault root is `INSITU_HOME` / `--vault` / `~/.insitu`. One vault per process.
- `materialize` writes `PROTOCOL.md` plus host adapters from `config/surfaces.yaml`, then mapped skill copies under host skill directories. Never clobber `AGENTS.md` or `CLAUDE.md`.
- Insitu never runs git and never shells out. Mutating tools write files and return the paths they wrote. Version-controlling a vault is the operator's business.
- One version number. `src/insitu/__init__.py` holds it, `pyproject.toml` derives it, and a test asserts `DESIGN.md` agrees.

## Privacy

This repo ships no real personal data. A vault holds someone's standing guidance, so treat vault contents as private by default.

- Docs, comments, examples, and tests use fictional vault vocabulary. `examples/vault/` is a fictional example vault, and it is the only one that ships.
- Do not commit a real vault's contents, filesystem paths, or project names.

## Layout

| Path | Role |
|------|------|
| `DESIGN.md` | Locked design spec |
| `src/insitu/` | Server package |
| `tests/` | pytest |
| `install/` | Global routers and MCP config examples |
| `examples/vault/` | Fictional example vault (tests and docs) |
