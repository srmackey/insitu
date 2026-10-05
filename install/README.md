# Install

These files ship with the Insitu server, not inside a user's vault.

Two jobs. Do not mix them.

**Start the server.** Upsert the block in `install/mcp.json.examples.md` into each enabled host.

**Use the server.** Place the user-global router from `install/routers/`. The project protocol is not this pass. `materialize` writes that from the same environment file.

The host list is `platforms.yaml`, next to `nexus.md`, in the folder `INSITU_ROOT` names. This page does not name hosts or their files. The stored definition is that home.

## When there is no environment file

Do not edit user-global server config. Do not copy a router into a user rules directory.

Project instructions land on `agents`. `materialize` writes `AGENTS.md` when that file is missing or already carries the Insitu stamp, plus `PROTOCOL.md`. An existing `AGENTS.md` without that stamp is left unchanged. `CLAUDE.md` is never written. No skill directory is created. An explicit `enabled: []` writes `PROTOCOL.md` only.

Recording the host this agent is running in is how a machine gets its first `enabled` name. Look up that one host's server file, key, format, and where it loads user-global instructions. Write them into `platforms.yaml`. Set `enabled` to that one name. Do not search the profile for other hosts. Then run the pass below for that name only.

## Pass

Read `platforms.yaml`.

For each name in `enabled`:

- No stored definition: look up that host's real server file, key, format, and user-global instruction location. Write them under `platforms`. Do not paste paths from memory. Then continue.
- Server: for each `server` entry, open `path` and upsert the block under `key`, serialized as `format`. Leave every other key in that file alone.
- Router: for each `instructions` entry with `scope: user`, the directory of `path` is where that host loads a user-global rule. Write `insitu-router` plus that file's extension into the directory. The body is `install/routers/<platform>.md` or `install/routers/<platform>.mdc`, whichever matches the extension. Copy it as it is. If that file does not exist, skip the router and still upsert the server block. Do not replace another product's file.

Skip a definition you cannot apply, say which one, and continue with the other names.

Project-scoped `instructions` and `skills` entries are `materialize`, not this pass.

`install/AGENTS.md` is a sample constitution. Copying it is by hand. `materialize` writes a project's `AGENTS.md` only when that file is missing or already stamped, and it never writes `CLAUDE.md`.

## Maintenance

Add, remove, and a moved checkout all run the pass above.

**Add.** Put the name on `enabled`. Run this pass, and the same pass for each other public product already installed. The pass writes a missing definition before it upserts. Then `materialize` the running projects.

**Remove.** Take the name off `enabled`. Dry-run first. For that name's server entries, list this product's key under `key`, and list the user-global router file this product wrote. Write nothing. Every other key in the host file stays. On the real remove, delete only those keys and that router file.

**Path refresh.** The checkout moved. Run the pass again so this product's block uses the current path. Upsert this product's key. Leave every other key alone.
