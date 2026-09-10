# AGENTS.md — Insitu

Guidance for agents and contributors working in this repo.

**Product.** Insitu is a portable MCP server for situated identity: who you are *here*. It stores reusable articles, roles, skills, and versioned packs, and composes a project-specific protocol.

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
- `materialize` writes the composed protocol and host adapters from `config/surfaces.yaml`. It never clobbers `AGENTS.md` or `CLAUDE.md`.
- Insitu never runs git and never shells out. Mutating tools write files and return the paths they wrote. Version-controlling a vault is the operator's business.
- One version number. `src/insitu/__init__.py` holds it, `pyproject.toml` derives it, and a test asserts the DESIGN header agrees.

## Privacy

This repo ships no real personal data. A vault holds someone's standing guidance, so treat vault contents as private by default.

- Docs, comments, examples, and tests use fictional vault vocabulary. `examples/vault/` is a fictional example vault, and it is the only one that ships.
- Do not commit a real vault's contents, filesystem paths, or project names.

## Layout

| Path | Role |
|------|------|
| `DESIGN.md` | How the system is structured and how it works |
| `src/insitu/` | Server package |
| `tests/` | pytest |
| `install/` | Global routers and MCP config examples |
| `examples/vault/` | Fictional example vault (tests and docs) |

## Public repo

This checkout is public. Do not run `git add -A`, `git add .`, or `git add -u`. Stage paths by name.

Enable the hygiene hook in each clone: `git config core.hooksPath .githooks`. The denylist lives in `.git/hygiene-denylist` (untracked).
