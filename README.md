# Insitu

Situated identity for agents: who you are *here*.

Insitu is a portable MCP server. One vault holds the reusable pieces of how an agent should work with you. A project map names which of those pieces apply in this folder. The server composes them into a protocol and writes that core into files the host already loads.

The vault holds five kinds of thing:

- **Stanzas.** Standing guidance (tone, method, review, identity that changes how the agent operates). One markdown file each.
- **Roles.** Named packs of stanzas a kind of project includes as a unit (`node`, `repo`, and the like).
- **Projects.** A map per working folder: core stanzas, on-demand stanzas, imported packs, and skills.
- **Skills.** Procedures the host should expose as `/name`. Mapped on the project. Copied into host skill directories on `materialize`. Not concatenated into the protocol.
- **Packs.** Versioned capabilities authored outside the vault (system-development, multi-platform, and the like). Installed onto a shelf, then imported by a project.

You already have directions for how an agent should work with you. The pain is reuse. The same guidance needs to show up in more than one place, but not the same set every time. Copies drift. A new repo starts without the ones you meant to bring. You notice after the agent has already gone the wrong way.

Size reports on stanzas and on the composed protocol tell you when to trim. Skills have their own size summary. They do not go into the protocol token count.

## How it works

- A **stanza** is one markdown file of standing guidance.
- A **role** is a named, ordered pack of stanzas a project can include as a unit.
- A **project map** selects stanzas as core (always loaded) or on-demand (pulled when the work needs them), plus imported packs and mapped skills.
- A **protocol** is composed, never a catalog row. `materialize` writes `PROTOCOL.md` plus host adapters so the core is in the session. `resolve_protocol` inspects the same composition.
- A **skill** is a procedure the host discovers as `/name`. `materialize` copies mapped skills into `.grok/skills/`, `.claude/skills/`, and `.cursor/skills/`.
- A **pack** is a versioned bundle on the vault shelf (`library/<id>/<version>/`). `install_capability` / `install_stanza` pull it and write this map. A single-stanza install may land in `core` or `on_demand`.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/srmackey/insitu.git
cd insitu
uv sync
uv run pytest
```

`uv run insitu` starts the server on stdio.

### Vault

One vault per process, resolved in this order:

1. `INSITU_HOME`
2. `--vault /path/to/vault`
3. `~/.insitu`

A vault is folders on disk (`stanzas/`, `skills/`, `provenance/`, `projects/`, optional `roles/`, `library/`, and `config/`). This repo ships a sample vault:

```bash
uv run insitu --vault examples/vault
```

Keep a personal vault outside the checkout.

### Add the server to a host

See `install/mcp.json.examples.md` for Cursor, Claude Code, and Grok. Typical shape:

```json
{
  "mcpServers": {
    "insitu": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/insitu", "insitu"],
      "env": { "INSITU_HOME": "/path/to/your/vault" }
    }
  }
}
```

### Routers (once, user-global)

A router tells the host that Insitu exists. It is not the project protocol. It also says: rematerialize the generated pack if it is missing or stale; retrieve the multi-platform pack and write other missing host files.

| Host | Copy from | Copy to |
|------|-----------|---------|
| Cursor | `install/routers/cursor.mdc` | `~/.cursor/rules/insitu-router.mdc` |
| Claude | `install/routers/claude.md` | `~/.claude/rules/insitu-router.md` |
| Grok | `install/routers/grok.md` | `~/.grok/rules/insitu-router.md` |

Optional: paste `install/AGENTS.md` into a constitution file by hand. `materialize` never writes `AGENTS.md`, `CLAUDE.md`, or `CLAUDE.local.md`.

Enable host adapters in the vault with `config/surfaces.yaml` (`grok`, `claude`, `cursor`). From a project checkout, call `materialize`. That writes `PROTOCOL.md` plus adapter files under `.grok/rules/`, `.claude/rules/`, and `.cursor/rules/`, and generated skill copies under `.grok/skills/`, `.claude/skills/`, and `.cursor/skills/` for each mapped skill.

## Working with an agent

Once the server, vault, and router are in place, you talk to the agent in the project folder. Insitu keys the project off that folder's name.

**First time in a checkout.** Ask the agent to materialize this project's protocol. That writes `PROTOCOL.md`, the host adapter files, and mapped skill copies. Constitutions and other host files this host loads are not that output; the router retrieves the multi-platform pack and writes those if they are missing. Later sessions load the core on their own. Do not edit the generated protocol or skill files. Change a stanza, skill, or the project map in the vault, then materialize again.

**Day to day.** The core is already in the session. Treat it as binding. Mapped skills are already in the host skill directories; treat `/name` as binding. Some stanzas are only *on-demand*: listed, not loaded. When the work needs one, ask the agent to pull it. You can name the guidance ("use summary-first") instead of a path.

**A new project.** Ask what stanzas, roles, skills, and packs exist. Pick the set this project should carry. Install a capability if this folder should use a whole pack. Then materialize. The point is a deliberate subset, not a paste of everything.

**When something feels off.** If the protocol is missing, stale, or heavier than it should be, ask the agent for Insitu status of this folder (`project_status`) or to inspect the composition and the size report. Rematerialize after you trim or change membership.

**Add or update.** If you find yourself repeating instructions, name and create a new stanza (or a skill, if it should be a `/name` procedure). Link it to one or more roles or projects. Instructions not working as expected? Find the stanzas or skills in use and update the right one.

## Tools

```text
# after a vault or map change
materialize                 # PROTOCOL.md + host adapters + mapped skill dirs

# agent, live
project_status              # folder inspect card (map, sourced ids, disk). not session start
resolve_protocol            # inspect weight, compare to the materialized header
get_stanza ...              # pull an on-demand stanza
list_on_demand              # non-core index for this project

# catalog
list_stanzas                # what exists, and how heavy each piece is
list_skills                 # skill catalog (not session start)
list_roles / list_projects / list_packs
get_project                 # how heavy is this project's protocol?
get_skill / get_role / get_pack

# authoring
create_stanza / update_stanza
link_stanza / unlink_stanza # project maps only; target core or on_demand
create_skill / update_skill / delete_skill / where_used_skill
link_skill / unlink_skill
create_role / update_role   # member add/remove is preview then confirm
create_project / update_project
install_capability / install_stanza / install_skill
uninstall_capability / uninstall_stanza / uninstall_skill
delete_stanza / delete_role / delete_project
                            # delete is user-gated: preview, then confirm
                            # mutations write files and report them in `files`
                            # Insitu never runs git; tracking the vault is yours

# vault admin
fetch_pack / remove_pack    # seed or drop a shelf version
validate / where_used
operators                   # classes, admins, default (inspect)
grant / revoke              # admin only; first admin is CLI-only
```

Every mutating tool takes `working_folder`. A **bound** chair (the default) may
write only the map whose key matches that folder's basename; an **admin** chair
may name another.

Stanzas, roles, and skills belong to no single map, so they are gated by reach
instead: creating is always allowed, and editing or deleting one is refused once
a map other than yours composes it. Editing a role is the sharp case, since its
membership reaches every map that carries it. A vault with no
`config/operators.yaml` runs pre-init: writes go through as before and the
result says how to fix it.

```
insitu init --admin <project-key>   # register the first admin; refuses if one exists
insitu operators                    # show the config
insitu                              # start the MCP server (unchanged)
```

## Develop

```bash
uv sync
uv run pytest
uv run insitu
```

See `DESIGN.md` for the spec.

## License

MIT. See `LICENSE`.
