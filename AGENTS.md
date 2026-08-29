# AGENTS.md — Insitu

Canonical constitution for the Insitu server repo. Claude loads it via the thin `CLAUDE.md` shim. Edit this file, never the shim.

**Product.** Insitu is a portable MCP server for **situated identity**: who you are *here*. It stores reusable **stanzas**, **roles**, project-mapped **skills**, and versioned **packs**, and composes a **project-specific protocol**. Complementary to ContextForge (system/dev context). Not a second brain.

**Design lock.** `DESIGN.md` is the locked spec (v0.13, 2026-08-29). Implement against it. Role and project authoring, user-gated delete, validate findings, the `provenance/` why-log tree, the on-demand rename, pack-install (0.9), `project_status` (0.10), skills (0.11), pack-skill install (0.12), and operator classes plus the on-demand install grain (0.13) are in `src/`. Do not expand past it (search, ACL, rename tools, nested roles, role-carried skills) without an explicit design change.

**Session entry.** Read `STATUS.md` and state the Forefront before other work. Live next-step lives there, not in this file.

## Agent stance

You are a careful steward of a small, markdown-first MCP. Files on disk are the truth. Git is a safety net, not a versioning product. Prefer the existing primitives (stanza, project map, `resolve_protocol`) before adding new ones.

## Stack

- Python 3.11+, `uv`, FastMCP, Pydantic v2
- Markdown + YAML frontmatter on disk; no required database in v1
- Tests with pytest under `tests/`
- `uv sync` / `uv run pytest` / `uv run insitu`

## Invariants

- A **protocol** is composed, never a catalog row. Session start is `resolve_protocol`.
- A **stanza** is one markdown file under the user's vault `stanzas/`. Why-logs live under `provenance/<id>.md` and are not stanzas. Leftover `*.prov.md` under `stanzas/` is also not a stanza.
- Project key = working folder basename = `projects/<folder>/`. Missing project is a structured miss, not a catalog scan.
- Vault root is `INSITU_HOME` / `--vault` / `~/.insitu`. One vault per process.
- `materialize` writes `PROTOCOL.md` plus host adapters from `config/surfaces.yaml`, then mapped skill copies under host skill directories. Never clobber `AGENTS.md` or `CLAUDE.md`.
- Personal vault contents (real `about-me`, anything from sibling projects) do not belong in this public repo, and neither do sibling project names, real vault topology, or the operator's own paths. Use fictional names in docs, comments, examples, and tests. Ship a fictional `examples/vault/` only.

## Layout (this repo)

| Path | Role |
|------|------|
| `DESIGN.md` | Locked design spec |
| `src/insitu/` | Server package |
| `tests/` | pytest |
| `install/` | Global routers + mcp examples (not user-vault data; not the protocol pack) |
| `examples/vault/` | Fictional example vault (tests and docs) |
| `inbox/` | Node arrival tray. Process on command. |
| `STATUS.md` | Nexus-facing where / next (local; not shipped) |
| `_system/` | System-development method tree (local; gitignored). Pack orchestrator: `methodology/system-home`. |
