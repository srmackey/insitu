# Insitu — Design Spec

**Version 0.13 · locked 2026-08-29** (supersedes 0.12 · 2026-08-26)

Operator classes gate the mutating map tools, and the stanza install grain reaches `on_demand` (0.13). Skills are first-class vault objects (0.11). Pack-delivered skills install like pack stanzas (0.12). `project_status` remains 0.10. Pack-install remains 0.9. Python package version is `0.12.0` until 0.13 ships. Detail is kept with the author, not in this repo.

Product name: **Insitu** (situated identity: who you are here). Working title during design was Protocol Vault. A **stanza** is a portable section of standing guidance. A **skill** is a procedure the host should expose as `/name`. A **protocol** is the assembled, project-specific "who I am here."

---

## 1. Purpose

Insitu is a portable MCP server for **situated identity**: who you are *here*.

One vault holds reusable **stanzas** of standing agent guidance, **roles** that group them, **skills** the host should expose as `/name`, and versioned **packs** a project can install. A **project map** names which of those belong in this folder. `resolve_protocol` composes that set. `materialize` writes the composed core into files the host already injects at session start, plus mapped skill copies under host skill directories.

It solves the common problem of working-with-me guidance being scattered, duplicated, and drifted across projects and hosts (Cursor rules, `AGENTS.md`, `CLAUDE.md`, skill trees, and the rest) by:

- Keeping every reusable stanza and skill in one vault
- Letting each project declare exactly which stanzas, roles, packs, and skills belong here
- Writing the composed core and mapped skills into files the host already loads (`materialize`)
- Giving agents `project_status` and `resolve_protocol` to inspect the same composition, `get_stanza` to pull on-demand pieces, and `get_skill` to inspect a skill body

If the composed pack never sits in the loaded constitution, Insitu is a filing cabinet. Host injection is a v1 kill condition, not a polish item.

The first user is local. The system is structured so someone else could adopt it. It is not an enterprise product.

---

## 2. Scope & Boundaries

Insitu owns **user operating context**: who the user is *as it affects how an agent should work with them*, how they want to be worked with, the methodologies and interaction principles they apply across projects, and other durable guidance that belongs in the loaded operating text.

**Inclusion test (host-document test).** A file is a stanza if you would put it in a Cursor rule, an `AGENTS.md`, or a `CLAUDE.md` so the agent operates differently toward you or the work. Style, method, constraint, and interaction-relevant identity (`about-me`) are kinds of content, not different kinds of object. A movie log or a full biography fails the test: that is wiki or primer material, not a stanza.

A **skill** is a procedure the host should expose as `/name`. It is not a stanza. Concatenating it into `PROTOCOL.md` would not create a slash command. See the Skill row in §3 and the 0.11 fold below.

Insitu does **not** model engineering or system context: repository knowledge, component ontologies, system facts (auth, security posture, integration quirks), or cross-repo task composition. That is the domain of a dev-context system (in the reference deployment, ContextForge). The two are complementary and are expected to run side by side as separate MCP servers.

Rule of thumb: if it describes *how to work with the user*, it belongs in Insitu; if it describes a *system*, it belongs in the dev-context tool. Gray zone (for example "I prefer pytest"): treat as a stanza unless it is a fact about a specific repo.

---

## 3. Core Concepts

| Concept | Definition |
|---------|----------|
| **Stanza** | One portable section of standing agent guidance. A markdown file in the vault. Composed into a protocol. Ops slang: a config is made of stanzas. |
| **Protocol** | The assembled, project-specific "how to work with me" document. Not stored as an authored source file. Produced by `resolve_protocol` and written by `materialize` to `PROTOCOL.md` plus host adapters. Hosts each have their own name for the equivalent loaded text (rule, constitution, `CLAUDE.md`). |
| **Project** | A named binding that selects which stanzas make up a protocol. The project key is the directory name under `projects/`. |
| **`_global`** | A distinguished project whose composed core is automatically included in every other project's protocol (unless the project opts out). Keep it very small: only stanzas that truly transcend projects. |
| **Role** | A named, ordered pack of stanzas. A project includes a role instead of listing every member. Membership lives in `roles/<id>.yaml`. Stanzas declare the same id in frontmatter so drift is visible. |
| **Core** | Stanzas always injected into the protocol. |
| **On-demand** | Stanzas associated with a project but only loaded when the work needs them (`get_stanza`). Their titles and descriptions are surfaced on the resolved protocol so agents know what they can pull. |
| **Pack** (0.9) | Versioned bundle of stanzas and roles, authored outside the vault. Installed copy lives under `library/<id>/<version>/`. Optional `skills/` on a pack is copied onto the shelf. `install_skill` (0.12) maps a listed skill; whole-capability install does not attach skills. |
| **Library** (0.9) | Vault shelf of pulled pack versions. Not native `stanzas/`. |
| **Import record** (0.9) | A project map entry: this node uses a whole **capability** or listed **stanzas** from pack id at `version` or `latest`. |
| **Skill** (0.11) | A procedure the host discovers as `/name`. Vault object under `skills/<id>/SKILL.md`. Membership is `map.yaml` `skills:` only. Roles do not carry skills. `_global.skills` is not inherited. |

---

## 4. Vault Layout

```text
vault/
├── stanzas/                      # all stanzas live here
│   ├── interaction/
│   │   ├── summary-first.md
│   │   └── how-i-work-with-ai.md
│   ├── methodology/
│   │   └── ai-system-development.md
│   ├── knowledge/
│   │   └── about-me.md
│   └── ...
├── provenance/                   # why-logs; same path as the stanza id
│   ├── interaction/
│   │   └── summary-first.md
│   └── skills/                   # 0.11; why-logs for skills
│       └── close-books.md
├── skills/                       # 0.11; first-class skill objects
│   └── close-books/
│       ├── SKILL.md
│       └── scripts/              # optional; copied on materialize
├── roles/                        # named packs (0.5)
│   ├── clerk.yaml
│   └── steward.yaml
├── projects/
│   ├── _global/
│   │   └── map.yaml
│   ├── river-ledger/             # named after the working folder
│   │   ├── map.yaml
│   │   └── notes.md              # optional free-form project notes
│   └── ...
├── config/
│   ├── review-policy.yaml        # optional
│   ├── surfaces.yaml             # which host adapters materialize writes
│   └── pack-repos.yaml           # 0.9; optional; zero to many pack repos
├── library/                      # 0.9; pulled pack versions
│   ├── lock.yaml
│   └── <pack-id>/<version>/      # mini-vault: stanzas/, roles/, pack.yaml, VERSION
└── .git/                         # recommended; shows *what* changed
```

`materialize` writes into the **project checkout** (the working folder), not into the vault:

```text
<working-folder>/
├── PROTOCOL.md                   # portable canon (always written)
├── .grok/rules/insitu-protocol.md
├── .grok/skills/<id>/            # 0.11; generated copies
├── .claude/rules/insitu-protocol.md
├── .claude/skills/<id>/
├── .cursor/rules/insitu-protocol.mdc
└── .cursor/skills/<id>/
```

Only adapters listed in `config/surfaces.yaml` are written. See §10.

Install assets (routers, optional constitution hook, mcp examples) ship with the **server**, not inside each user's vault. See §10.

Folders under `stanzas/` (`interaction/`, `methodology/`, `knowledge/`) are a human convention. They are not a type system and do not change load behavior. **Roles** (`roles/*.yaml`) are a type system: they change composition. Do not treat a stanza folder as a role.

---

## 5. Project Identity

The project key **is** the directory name under `projects/`.

**Convention.** The working folder's basename is the project key. Mixed-case folder names fold to lowercase (`ProjectName/` loads `projects/projectname/`). Work in `river-ledger/` and the server loads `projects/river-ledger/`. No extra binding file is required for the common case.

**Labels, not identity.** `map.yaml` may carry `repo`, `name`, and `aka` for display and colloquial lookup. They do not change which project is selected.

**Miss.** If no `projects/<folder>/` exists, `resolve_protocol` returns a structured miss. It does not scan the stanza catalog and it does not return an empty protocol that looks like success. The miss should name the project key that was tried and the path that was missing.

**Vault root** is a server concern (`INSITU_HOME` or a startup flag), not a field on the project map. Pointing the process at another vault is how demos work (same idea as ContextForge's home override). A project lives inside a vault; it does not point at one.

**Charset.** Project keys, stanza path segments, role ids, pack ids, and skill ids: `a-z`, `0-9`, `-`. Skill ids are a single path segment (no `skills/methodology/land/`). `_global` is the only reserved `_` name. Reject `..`, absolute paths, and anything that would escape `stanzas/`, `provenance/`, `projects/`, `roles/`, `library/`, or `skills/`.

**Out of scope for v1:** a repo-local override file (for a checkout whose folder name is not the project key, or a per-repo vault pointer). Add it when a real checkout needs it.

---

## 6. Project Map Schema

```yaml
# projects/<folder-name>/map.yaml
repo: river-ledger                # repo identity (label)
name: River Ledger                # optional display name
aka: [rl, riverledger]            # optional colloquial names
roles:                            # optional; ordered role packs (0.5)
  - clerk
core:                             # ordered; always injected
  - interaction/how-i-work-with-ai
on_demand:                        # associated but not auto-injected
  - knowledge/deep-domain-x
  - methodology/specialized-y
imports:                          # optional; 0.9 capability / stanza installs
  - pack: system-development
    version: 0.1.0                # or latest; omit members = whole capability
  # - pack: voices
  #   version: 1.1
  #   stanzas: [identity/x]       # 0.13: core members
  #   on_demand: [identity/z]     # 0.13: indexed, not injected
skills:                           # optional; 0.11; omit when empty
  - close-books
include_global: true              # optional; default true. Set false to
                                  # exclude _global's composed core.
```

- Order in `roles`, then `imports`, then `core` (and in `_global`) is significant and is preserved in the resolved protocol.
- Paths are relative to the `stanzas/` directory and use `/` separators.
- `_global` uses the exact same schema, including `roles`. Its `on_demand` list is normally empty, and `include_global` is meaningless there. `_global` does not need `repo`.
- Free-form project context lives in the optional `notes.md` file, not in `map.yaml`.
- There is no `vault:` field on this file.

### 6.1 Role packs

A **role** is a named, ordered pack of stanzas. It is how a kind of project (clerk, steward, archivist) carries a shared set of rules without listing every member on every map, and without stuffing `_global`.

Roles are vault content, not server builtins. The server has no built-in role names.

**Why not a tag scan.** Stanza frontmatter alone cannot be the membership source: injection order must be explicit and stable, and adding a `roles: [node]` tag must not silently enlarge every node protocol. The role file is the membership list. Frontmatter is the label that `validate` checks against that list.

**On disk.** One file per role: `roles/<id>.yaml`. Missing `roles/` is empty (same idea as missing `_global`). Filename stem is the role id.

```yaml
# roles/clerk.yaml
name: Clerk                      # optional display name
description: Receive the inbox; propose cross-project notes upward.
core:
  - methodology/clerk-inbox
on_demand: []                     # optional; default empty
```

- `core` and `on_demand` use the same stanza-id rules as a project map.
- A role must not list another role. No nesting.
- Unknown extra fields are ignored on load (forward compatible) but `validate` may warn.

**Stanza frontmatter.** A stanza that belongs to a role declares it:

```yaml
roles: [node]
```

A stanza may list more than one role. `roles` on a stanza is optional until the stanza appears in a role file; then `validate` requires the matching declaration (see below).

**Project includes.** `map.yaml` `roles:` is an ordered list of role ids. A project may also list stanzas in `core` / `on_demand` as today. First occurrence wins when the same stanza appears in a role and again on the map.

**Resolution (replaces the §8 one-liner).**

```
global_composed = expand(_global.roles).core  +  _global.core     # if _global exists
                  # first-wins dedup

protocol.core =
    global_composed               # if include_global
  + expand(project.roles).core
  + expand(project.imports).core  # 0.9; empty if no imports
  + project.core
                  # first-wins dedup across the whole concatenation

protocol.on_demand =
    expand(project.roles).on_demand
  + expand(project.imports).on_demand
  + project.on_demand
                  # first-wins; never injected into core
```

`include_global` injects `_global`'s **composed** core (roles already expanded), not the raw `_global.core` list. `_global.on_demand` is still not pulled into other projects (unchanged from 0.4).

**Skills (0.11 / 0.12).** Native composed skills are `project.skills` (link). Pack skills are import records with a `skills:` list (`install_skill`). No role expand. No `_global` prefix, even when `include_global: true`. Whole-capability import records do not attach pack skills. Same skill id from native `skills:` and an import, or from two imports, is a hard error (`duplicate_import_skill`). Omit native `skills:` when empty; do not write `skills: []`. Unknown extra keys on a map stay ignored except `skills`, which 0.11 defines. A role file must not have a `skills` key (`role_skills_not_supported`). `_global.skills` is legal for the `_global` project itself and is a finding (`global_skills_not_inherited`) so authors see that other projects do not inherit it.

`expand(roles)` walks the project's `roles:` list in order and concatenates each role's `core` (or `on_demand`). Unknown role id is a hard error, same as a missing stanza. Later protocol entries still refine earlier ones, so `project.core` wins over a role, and a role wins over `_global`.

On load, a leftover `available:` key (and no `on_demand:`) is treated as `on_demand`. Mutations write `on_demand` only. Both keys on one file is an issue (`both_keys_present`). `validate` reports leftover `available:` as finding `legacy_available_key`; `fix=true` rewrites it.

### 6.2 Packs and library (0.9)

Pull, not push. A node **installs** a whole capability, a listed stanza, or a listed skill at a pack version (`install_capability` / `install_stanza` / `install_skill`). Insitu resolves: `library/<id>/<version>/` first, then `config/pack-repos.yaml` (zero to many; missing or empty is shelf-only). On hit, copy the pack interior onto the shelf and write **that** map. On miss: structured available-versions list, default newest; do not write the map. Does not inject other projects.

User-facing: “install capability X 1.0,” “install identity x at 1.1,” “install skill close-hatch at 0.1.0.” Not “pin a pack.” `fetch_pack` / `remove_pack` are vault admin (seed or delete a shelf version). `update_project` does not pull.

**Shelf.** `library/<pack-id>/<version>/` is a mini-vault (`stanzas/`, `roles/`, `pack.yaml`, `VERSION`, optional `skills/`). Pack-delivered skills stay on the shelf. `install_skill` maps one id onto this project; `materialize` writes host copies from that shelf version. Native vault skills stay 0.11 (`link_skill`). Whole-capability install does not attach the pack skill list. Multiple versions of one id sit side by side. `library/lock.yaml` inventories versions on disk. Native `stanzas/` / `roles/` / `skills/` are never merged into.

**Operator gate (0.13).** See §6.3. Pack install and uninstall are map writes and pass the gate. `fetch_pack` / `remove_pack` are vault-store admin and stay store-scoped.

**Local repo (v0).** A pack repo folder is a working copy with one `VERSION`. A repo query returns that version only. Older versions live on the shelf once pulled. Git tags later.

**`version` on a record:** semver (sticky) or `latest` (float on each resolve/materialize). Exact pin plus a newer copy: compose the exact pin, notice `newer_available`. Do not auto-upgrade. Do not force other nodes onto a newer version.

**Composition.** `expand(imports)` walks map records in order. Resolve `latest` first. Whole capability (no `stanzas` / `skills` keys): expand that version’s `roles/<pack>.yaml` like a native role. Stanza members: inject only those stanza files from that version. A record's `stanzas:` are core members and its `on_demand:` are indexed rather than injected, the same split a pack role expresses for a whole capability (0.13). Skill members (`skills:` on the record): compose those pack skills after native `project.skills`. Same stanza or skill id from two records on one project is a hard error.

```
protocol.core =
    global_composed
  + expand(project.roles).core
  + expand(project.imports).core
  + project.core

protocol.on_demand =
    expand(project.roles).on_demand
  + expand(project.imports).on_demand
  + project.on_demand
```

Native `roles:` never searches `library/`. `imports:` never searches vault `roles/`. `get_stanza` looks native `stanzas/` first, then this project’s import records at their versions.

**Unreferenced versions** (on disk, no map cites them, not the current target of `latest`): finding `unreferenced_version`. `fix` does not delete. `remove_pack` on confirm.

Detail, extra tools, and tests are kept with the author, not in this repo.

**`validate`.** In addition to 0.4 checks:

- Every `roles:` id on a map exists as `roles/<id>.yaml`.
- Every stanza id inside a role file exists.
- **Membership match:** if `roles/<id>.yaml` lists stanza S, S's frontmatter must include `id` in `roles:`. If S's frontmatter lists a role, that role file must list S (in `core` or `on_demand`). Mismatches are reported. `fix=true` writes the missing frontmatter role onto the stanza; it does **not** add a stanza to a role file (that would change every project using the role).
- Duplicate stanza ids inside one role file, and duplicates created only by expansion, are reported the same way as map dupes. Expansion itself already drops later copies.
- **Packs (0.9):** each exact `imports:` record has `library/<pack>/<version>/` on disk; listed `stanzas:` and `on_demand:` members exist in that tree; `unreferenced_version` is a finding (`fix` does not delete); broken exact pin is a hard error. Same stanza id from two import records on one project is a hard error.

**`where_used`.** A stanza is used by: project maps that list it in `core` or `on_demand`; role files that list it; project maps whose `roles:` or `imports:` expand to include it (report `lists: [role:<id>]` or `lists: [import:<pack>@<version>]`).

**Tools.** `list_roles` and `get_role` are authoring tools (parallel to `list_projects` / `get_project`). `get_role` returns the role file, member sizes, and which projects include it. `resolve_protocol` reports the role ids that were expanded (`roles: [node]`). `list_stanzas` may filter by role id. `link_stanza` / `unlink_stanza` stay one stanza on one project map. Role membership is `create_role` / `update_role` (add/remove on `core` and `on_demand` is preview then `confirm=true`). `delete_role` is user-gated the same way.

**Not a mode.** A role is composition, not a runtime hat. Including `node` means those stanzas are in the protocol. It does not switch Architect vs Maintainer or otherwise change tool privilege.

**Illustrative roles** (example shapes, not shipped defaults):

| Role | Typical members | On |
|---|---|---|
| `clerk` | `methodology/clerk-inbox` | every working project |
| `steward` | `methodology/steward-handoff` | the coordinating project |
| `archivist` | `methodology/archivist-inbox` | the reference project (with `clerk` as well) |

Those stanza files are authored in a vault. The role *mechanism* ships before any of them exist.

**`_global` vs roles.** `_global` stays the tiny "every project, always" prefix (reply shape, output voice). A role is "every project of this kind." Do not put role behavior on `_global` so you can skip roles. A project sets `include_global: true` only for true universals, then names its roles. A project that must not receive another kind's rules does not include that role.

---

### 6.3 Operator classes (0.13)

Two classes, stored in `config/operators.yaml` beside `pack-repos.yaml` and `surfaces.yaml`. Vault state, not install-folder state: `INSITU_HOME` moves and the code checkout is shared. This is a discipline gate against casual cross-map writes, not a security boundary; the file is hand-editable by anything with a shell.

```yaml
default_class: bound
projects:
  river-ledger: admin
```

| Class | Mutate maps | `materialize` | Grant / revoke |
|---|---|---|---|
| **admin** | any project key | any working folder | yes |
| **bound** (default) | this project only | this folder only | no |

**The calling chair** is the basename of `working_folder`, case-folded. All thirteen mutating map tools require it: `link_stanza`, `unlink_stanza`, `link_skill`, `unlink_skill`, `install_capability`, `uninstall_capability`, `install_stanza`, `uninstall_stanza`, `install_skill`, `uninstall_skill`, `create_project`, `update_project`, `delete_project`. A bound chair whose key is not `project` gets `chair_bound`. `materialize` already took `working_folder` and joins the same gate; naming no project means this folder's own map, which is always allowed.

**Inspect stays free.** `list_*`, `get_*`, `where_used`, `validate`, `project_status`, `resolve_protocol`, and `operators` may name another project. Vault-store tools (`create_stanza`, `fetch_pack`, `remove_pack`, pack authoring) stay store-scoped: they write the store, never another project's map.

**Pre-init.** No `operators.yaml` means the vault behaves as 0.12 did, and every gated result carries a warning naming the fix. Failing closed would lock every chair out of a vault with no admin registered to unlock it. `working_folder` is required either way: that half of the break is unconditional.

**Bootstrap** is `insitu init --admin <key>` on the command line, guarded to succeed only when no admin exists. Deliberately not an MCP tool, so an agent cannot claim admin mid-session. Bare `insitu` still starts the server.

**Grant and revoke** are MCP tools that refuse a non-admin caller. Revoking the only admin is refused (`last_admin`): it would leave a vault nobody can reconfigure, and `init` refuses once an admin exists.

Not multi-user ACL; it is not in v1.

## 7. Stanza Format

Stanzas are Markdown files with YAML frontmatter.

```markdown
---
id: interaction/how-i-work-with-ai
title: How I Work with AI
description: Standing interaction and collaboration preferences
tags: [interaction, core]
roles: [clerk]                    # optional; required once a role file lists this stanza
created: 2026-08-15
updated: 2026-08-16
---

# How I Work with AI

... content ...
```

- `id` must match the path relative to `stanzas/` (no `.md`).
- `title` and `description` are **required**. They are surfaced when listing stanzas and when advertising on-demand stanzas on a resolved protocol.
- Remaining frontmatter fields are optional but recommended.
- Content is ordinary Markdown. A stanza must not include or transclude another stanza. Composition happens only through project maps and role packs.
- The why-log for a stanza is `provenance/<id>.md` (see §11). It is not itself a stanza. `list_stanzas` / `validate` / resolution never scan `provenance/`. Leftover `stanzas/**/*.prov.md` files are also ignored.

---

## 8. Resolution Rules

When an agent asks for the protocol of a project, compose per §6.1:

```
protocol = global_composed  +  expand(project.roles).core  +  expand(project.imports).core  +  project.core
           # global_composed omitted when include_global is false
```

- **Order is preserved** (`_global` composed first, then each listed role, then imports, then project `core`). Order is injection order. Where guidance conflicts, later entries refine or override earlier ones, so project-specific stanzas take precedence over roles and imports, and roles take precedence over `_global`.
- **Duplicates:** if a stanza appears more than once across `_global`, roles, imports, and `project.core`, the first occurrence wins and later occurrences are dropped. `validate` reports duplicates; it removes them only with `fix=true` (map-local copies only; role files are not rewritten by `fix`).
- **Missing `_global`:** treat as empty global core. Do not fail the vault. A fresh clone resolves before anyone writes `_global`.
- **Missing `roles/`:** treat as no role packs. A map that names a role then fails (hard error).
- **Missing stanza or role references are a hard error.** If any map, including `_global`, or any role file references a stanza that does not exist, or a map names a role that does not exist, resolution fails with an explicit error naming the broken reference. Determinism over convenience.
- **An unparseable file is a hard error naming that file.** A malformed stanza, skill, role, map, lock, pack, or `config/` file fails with its own path and the parse position (`VaultReadError`), wherever it is read. One bad file is never skipped silently, and the caller never gets a bare parser message that does not say which file it came from. Pack trees count: content Insitu did not author still gets named, not swallowed. Same principle as a broken reference.
- **Syntax and semantics fail differently.** A file that will not parse raises `VaultReadError`. A file that parses but carries a bad value keeps its existing structured miss (`invalid_review_policy`, unknown surface name, and the like). Do not collapse the two: the first says the file is unreadable, the second says it was read and is wrong.
- On-demand stanzas are **not** included in the protocol content. The resolved protocol **does include an index** of `expand(project.roles).on_demand` plus `expand(project.imports).on_demand` plus the project's `on_demand` list (id, title, description, size) so the agent knows what it can request via `get_stanza`.
- **Skills index (0.11 / 0.12).** After the on-demand index, `resolve_protocol` lists composed skills (`id`, `name`, `description`, size): native `project.skills` then pack import `skills:` lists. No skill `content`. Skill text is never injected into `core`. Missing skill id on a map is a hard error (`missing_skill`), same as a missing stanza. Duplicate native-and-pack or two-pack ids is `duplicate_import_skill`. Size totals stay stanza-only; `skills_size` (count, bytes, estimated tokens) is a separate skill-index summary.
- The resolved protocol reports **size metadata** on the result *before* the core bodies: stanza count, total bytes, and estimated tokens (`chars / 4`, labeled an estimate), plus the same fields on each core stanza. Size is an authoring surface, not just telemetry: a user (or an agent helping them) should be able to see protocol weight and trim stanzas before they bloat every session.
- Aliases (`name`, `aka`) do not select a protocol in v1. They are for `list_projects` and for an agent that heard "RL" and needs to know it means `river-ledger`.

---

## 9. MCP Tool Surface

| Tool | Description |
|------|-------------|
| `resolve_protocol` | Return the project protocol per §8: ordered core stanzas (content + metadata), the `on_demand` index, **the skills index**, **expanded `roles`**, and size totals. **Live / inspect tool:** weigh the composition, refresh mid-session, compare against a materialized header. Not how core guidance enters the session. |
| `get_stanza` | Return a single stanza (content + metadata, including size/tokens) by path/id. |
| `list_stanzas` | List all stanzas in the vault with metadata including title, description, tags, **roles**, **size and estimated tokens**. Optional path prefix / tag / role filters. **User bootstrapping / authoring tool:** a user in a new project lists stanzas to decide what to `link_stanza`, and uses the size fields to see what needs editing. Not agent-session bootstrap. |
| `list_projects` | List all projects (including `_global`), including `repo` / `name` / `aka` when present. Each row includes the composed-protocol size summary (see `get_project`) so a user can compare protocol weight across projects. |
| `get_project` | Return a project's map, notes, **roles**, **skills**, a **protocol size summary** (stanza count, total size, estimated tokens), and a **skills size summary**, without returning protocol content. Authoring check: "how heavy is this project's protocol?" |
| `project_status` | **0.10.** Folder inspect card. Required `working_folder`, optional `project` (default: folder basename). Map, sourced core ids, composed size, on-demand ids, disk freshness, plus a `card` string. No stanza bodies. Inspect only: never writes. Not session start. |
| `list_roles` | List role packs (`roles/*.yaml`) with id, name, description, member counts, and composed size of each role's `core`. Authoring tool. |
| `get_role` | Return one role file, member stanza metadata and sizes, and the project keys that include it. |
| `list_on_demand` | List the on-demand stanzas associated with a project (id, title, description, size). |
| `link_stanza` | Add a stanza to a project's `core` or `on_demand` list (subject to review policy). Writes immediately and reports `affects_projects`. |
| `unlink_stanza` | Remove a stanza from a project's map (subject to review policy). Writes immediately and reports `affects_projects`. |
| `create_stanza` | Create a new stanza (subject to review policy). Does not auto-link. `affects_projects` is empty. |
| `update_stanza` | Update an existing stanza (subject to review policy). Surfaces `where_used` and `affects_projects` so the blast radius is visible. |
| `delete_stanza` | User-gated delete. Preview (no write) unless `confirm=true` with the preview's `expected`. Unlinks from role files and direct maps, then deletes the stanza and its why-log. |
| `create_role` | Create `roles/<id>.yaml`. New role is on no project. `affects_projects` is empty. |
| `update_role` | Incremental. Name/description write now. Member add/remove is preview unless `confirm=true` with `expected`; confirm writes the role file and stanza `roles:` frontmatter. Maps do not change. |
| `delete_role` | User-gated delete. Confirm drops the id from maps, strips member frontmatter, and deletes the role file. |
| `create_project` | Create `projects/<key>/map.yaml` and optional `notes.md`. Creating `_global` when missing is allowed. |
| `update_project` | Incremental project-map edit. Attach/detach role writes immediately and reports members, composed weight, and `affects_projects`. |
| `delete_project` | User-gated delete of `projects/<key>/` only. Stanzas and roles stay. `_global` cannot be deleted (`cannot_delete_global`). |
| `where_used` | List every project map (core, on-demand, or via a role) and every role file that references a given stanza. |
| `validate` | Vault health check: verifies every referenced stanza and role exists, ids match paths, required frontmatter is present, role membership matches frontmatter (§6.1), and reports duplicate map entries. Read-only by default (safe to run any time). `fix=true` applies safe repairs (drop duplicate map entries; write missing `roles:` onto stanza frontmatter) and follows the review dial. **Findings** (`empty_projects`, `empty_roles`, `unreferenced`, `not_in_any_protocol`) are authoring hygiene: they never fail `ok` and `fix` never consumes them. |
| `materialize` | **Enforcement path.** Resolve per §8 and write `PROTOCOL.md` plus one generated file per enabled host surface (§10), then generated skill copies for each mapped skill. Never writes `AGENTS.md`, `CLAUDE.md`, or `CLAUDE.local.md`. Files carry a generated-file header (vault root, vault git ref if any, timestamp, project key, stanza ids in order) for staleness detection. Skill copies stamp after frontmatter. |
| `list_skills` | **0.11.** Vault catalog: id, name, description, size, which projects list it. Optional prefix filter. Not session start. |
| `get_skill` | **0.11.** One skill: frontmatter, content, size, payload file list (`scripts/`, `references/`). |
| `link_skill` / `unlink_skill` | **0.11.** Add or remove `skill_id` on `project.skills`. Writes now. `affects_projects`. |
| `create_skill` | **0.11.** Create `skills/<id>/SKILL.md`. Does not auto-link. Optional `why` writes `provenance/skills/<id>.md`. |
| `update_skill` | **0.11.** Update `SKILL.md` frontmatter and/or body. Surfaces `where_used` and `affects_projects`. |
| `delete_skill` | **0.11.** User-gated. Preview unless `confirm=true` with `expected`. Unlinks maps, deletes `skills/<id>/` and provenance. |
| `where_used_skill` | **0.11.** Every project map that lists the id in `skills:`. Roles never appear. |
| `list_packs` | **0.9.** Shelf inventory: pack ids, versions, which maps use which, unreferenced versions. |
| `get_pack` | **0.9.** One pack id: versions on disk, manifests, pins. |
| `install_capability` | **0.9.** This project uses the whole pack at `version` or `latest`. Pull onto the shelf if needed. User-facing: “install capability X 1.0.” Does not attach pack skills. |
| `install_stanza` | **0.9.** This project uses one stanza from a pack version. User-facing: “install identity x at 1.1.” **0.13:** `target` is `core` (default) or `on_demand`, mirroring `link_stanza`. |
| `install_skill` | **0.12.** This project uses one skill from a pack version. User-facing: “install skill X at 1.1.” Does not copy into native `skills/`. |
| `uninstall_capability` / `uninstall_stanza` / `uninstall_skill` | **0.9 / 0.12.** Drop this map’s record (or that member) only. Shelf unchanged. |
| `fetch_pack` | **0.9 admin.** Seed `library/<id>/<version>/`. No map change. |
| `remove_pack` | **0.9 admin.** Preview then confirm. Remove a shelf version (or all versions of an id). |
| `operators` | **0.13 inspect.** Operator classes, registered admins, default class. Warns when the vault is pre-init. |
| `grant` / `revoke` | **0.13 admin only.** Set a project's class, or drop it to the default. Refuses a bound caller. `revoke` refuses the last admin. Registering the first admin is CLI-only (`insitu init --admin`). |

Native vault skills use `link_skill`. Pack skills use `install_skill`. `link_stanza(..., target="skills")` remains `invalid_target`.

There is no `list_protocols` or `get_protocol`. A protocol is not a catalog row. It is what `resolve_protocol` returns and what `materialize` writes.

Every write result includes `affects_projects`. Previews may include the same list. After an authoring write, if the working-folder basename is in that list, rematerialize and start a new session. Agents do not delete: do not call `delete_*` unless the user explicitly asked to delete that object. Findings are not a cleanup prompt.

Every mutating map tool takes `working_folder` (0.13, §6.3). Inspect tools do not.

Deliberately absent: `rename_stanza` / `rename_role` / `rename_project`, which are not in v1. Registering the first admin is not a tool; it is `insitu init --admin` on the command line.

---

## 10. Agent Integration & Install

MCP cannot put text into the system prompt. Only the host can. A constitution line that says "call `resolve_protocol`" is a pull, and the tool result is retrieved text, not standing instruction. Core protocol therefore enters the session through **files the host already auto-loads**. `materialize` is that path. MCP stays for inspect, on-demand, authoring, and "this header is stale."

Two artifacts, different jobs. Do not mix them.

| Artifact | Job | Scope | Written by |
|----------|-----|-------|------------|
| **Router** | Insitu exists. Treat the generated protocol as binding. `get_stanza` for on-demand. Rematerialize if the header is stale. If other host files this host loads are missing, retrieve the multi-platform pack and write them. `list_stanzas` is the catalog and sizes (include or trim), not session start. | User-global (every project on this machine) | Install once, from `install/routers/` |
| **Protocol pack** | The composed `core` text for *this* project | The working folder | `materialize` |

The router is the ContextForge `contextforge-router.mdc` shape: small, almost never changes, does not contain the knowledge. The protocol pack is the composed core. Other host files (constitutions, skill trees, this-node bits) are not `materialize` output. If they are missing, the router tells the agent to retrieve the multi-platform pack and write them here. A global protocol pack would put the wrong "who I am here" into the wrong tree.

Hard rules that must fire even if Insitu is down (privacy, never-fabricate, discretion) stay in the hand-authored constitution. Materialize never edits those files.

### 10.1 Surfaces config

Which host adapters `materialize` writes is a vault-level fact (which agents this instance actually runs), not a per-project fact.

```yaml
# config/surfaces.yaml
surfaces:
  - grok
  - claude
  - cursor
```

Known names in v1: `grok`, `claude`, `cursor`. Unknown names are a hard error on `materialize`.

If the file is missing, write `PROTOCOL.md` only and return a structured warning `no_surfaces_configured`. Detection of existing `.grok/`, `.claude/`, or `.cursor/` trees may be used as a hint in the warning. It does not write adapters. The file is the lock.

A work vault and a home vault can list different surfaces.

### 10.2 Materialize outputs

`materialize` always writes `<working-folder>/PROTOCOL.md`. That file is the portable canon: humans read it, adapters are derived from it, non-MCP environments consume it. Repo-root `PROTOCOL.md` is **not** auto-loaded by Grok, Claude Code, or Cursor. It is not the injector.

In the same call, for each name in `surfaces.yaml`, write the adapter below. All adapters are **full-body copies** of the composed core (plus the generated header). Pointers (`@PROTOCOL.md`) are allowed only where a host expands `@path` at launch (Claude Code). v1 still writes a full body for Claude so every enabled surface is deterministic without depending on import expansion.

| Surface | Path (under working folder) | Format |
|---------|-----------------------------|--------|
| `grok` | `.grok/rules/insitu-protocol.md` | Full markdown. Grok does not expand `@path` imports. A file whose body is `@PROTOCOL.md` would inject that string, not the pack. |
| `claude` | `.claude/rules/insitu-protocol.md` | Full markdown. **No** `paths` frontmatter (a `paths` field would make it on-demand). Official Claude Code docs: rules without `paths` load at launch at the same priority as `.claude/CLAUDE.md`. Confirm once in dogfood with `/context` → Memory files. |
| `cursor` | `.cursor/rules/insitu-protocol.mdc` | Full body after YAML frontmatter `alwaysApply: true` and a short `description`. A plain `.md` in this folder is ignored by Cursor. |

`materialize` never writes `AGENTS.md`, `CLAUDE.md`, or `CLAUDE.local.md`. A one-line `@PROTOCOL.md` in an existing `CLAUDE.md` is a human (or one-time install) edit, not a `materialize` output.

Do not gitignore the host adapters if they must load. Grok skips gitignored instruction files during discovery. Personal or work-unsafe content in a committed adapter is a vault-composition problem (use a work-safe vault / work-safe `core`), not a gitignore problem.

**Skills (0.11).** After protocol adapters, for each enabled surface and each composed skill id, write allowlisted files (`SKILL.md`, `scripts/`, `references/`) to `.grok/skills/<id>/`, `.claude/skills/<id>/`, and `.cursor/skills/<id>/`. `SKILL.md` is the vault file with a generated stamp inserted after the closing frontmatter fence, before the body. Frontmatter stays otherwise byte-identical. Never write `~/.grok/skills/` or `~/.claude/skills/`. Never put skill bodies in `PROTOCOL.md`.

Orphan cleanup is stamp-scoped: under each enabled surface's skills root, if a subdirectory contains a `SKILL.md` whose body (after frontmatter) starts with the Insitu generated stamp, and that directory name is not in the composed skill list, delete that subdirectory. Leave every other directory.

No surfaces configured: `PROTOCOL.md` only, warning `no_surfaces_configured`. Do not write skill dirs. Add warning `skills_need_surfaces` when the project has a non-empty `skills:` list. Result payload includes `skills: [{id, paths}]` and `skills_removed: [{surface, id, path}]`.

Regenerate when the vault or the project map changes. A SessionStart hook that runs `materialize` is a freshness helper, not the injector: hosts usually read rules when the session starts, so a hook that writes after that helps the *next* session. Out of scope for v1 to ship such a hook.

### 10.3 Routers (install once)

Routers live in the **server repo** and are copied or symlinked into user-global rule dirs. They are not rewritten by `materialize`.

| Host | Install destination | Format |
|------|---------------------|--------|
| Cursor | `~/.cursor/rules/insitu-router.mdc` | `alwaysApply: true` (same as ContextForge's router) |
| Claude | `~/.claude/rules/insitu-router.md` | Markdown, no `paths` (user-level rules apply to every project) |
| Grok | `~/.grok/rules/insitu-router.md` | Markdown (Grok home rules already apply to every project) |

Ship the files under `install/routers/`. Also ship `install/mcp.json.examples.md` and an optional `install/AGENTS.md` hook snippet (10 lines, insurance, not the injector). The older single `install/insitu.mdc` that told the agent to call `resolve_protocol` first is superseded by this split.

Router body (all three hosts, same meaning):

- Insitu stores reusable stanzas and composes a project protocol.
- Project key is the working folder basename.
- The composed core is the generated host protocol file in this checkout (and `PROTOCOL.md`). Treat it as binding. Do not edit it.
- If that file is missing or its header is stale relative to the vault, call `materialize` (or `resolve_protocol` then `materialize`) before other work.
- `materialize` writes only the generated pack. It never writes `AGENTS.md` or `CLAUDE.md`. If other host files this host loads are missing, retrieve the multi-platform pack (`get_stanza` `platform/router-vs-pack` and this host's profile) and write them here. Do not put pack bodies in the router. If those stanzas miss, the pack is not installed; say so. Do not invent files the pack does not name.
- If the user asks Insitu status of this folder, call `project_status`. Do not walk `get_project`, `resolve_protocol`, or `get_role` for that readout. Do not call it at session start.
- Pull on-demand stanzas with `get_stanza` when the work needs one. Do not pull the on-demand list at session start.
- Use `list_stanzas` to see the catalog and sizes (what to include, what to trim). Do not call it at session start to load the core.
- Mapped skills are generated copies under the host skill directories (`.grok/skills`, `.claude/skills`, `.cursor/skills`). Treat them as binding for `/name`. Do not edit them. If a generated skill is missing or its stamp is stale relative to the vault, call `materialize`. Pull a skill body for inspect with `get_skill`. Use `list_skills` to see the catalog and sizes (what to attach). Do not call `list_skills` at session start to load skills. Host discovery is the load path.
- After an authoring write, if the working-folder basename is in `affects_projects`: call `materialize`, tell the user the loaded protocol is stale and they should start a new session, and do not continue as if the new stanza or role is already in core.
- Do not call `delete_stanza`, `delete_role`, or `delete_project` unless the user explicitly asked to delete that object. Do not treat `validate` findings as a reason to delete.

### 10.4 MCP after startup

Once the pack is in the host's auto-load path, agents do not need to call `resolve_protocol` for core compliance.

Use MCP for:

- `project_status`: folder inspect card (map, sourced ids, size, disk). Not session start.
- `resolve_protocol`: inspect, weight, mid-session refresh, compare to a materialized header
- `get_stanza` / `list_on_demand`: on-demand extras
- authoring tools, `validate`, `where_used`

Known limitation that remains: router-driven tool use (rematerialize on stale, pull on-demand) still depends on agent compliance and varies by host. Core load no longer does.

Facts this section depends on (verified 2026-08-16 unless noted):

- Grok auto-loads `*.md` under `.grok/rules/` and `$GROK_HOME/rules/`. It does not auto-load a repo-root `PROTOCOL.md`. It does not expand `@path` imports (Brain Forge agent profile, 2026-07-05, `grok inspect`).
- Claude Code loads `.claude/rules/*.md` without `paths` at launch; `~/.claude/rules/` is user-global. It reads `CLAUDE.md`, not `AGENTS.md`, and expands `@path` imports. Source: official Claude Code memory docs. Live `/context` probe in users's tree is still owed at dogfood.
- Cursor loads `.cursor/rules/*.mdc` with `alwaysApply: true`. Plain `.md` in that folder is ignored. It reads `AGENTS.md` natively (Brain Forge cursor profile, 2026-07-06).

---

## 11. Provenance & Review

**What vs why.** Git is recommended as a **safety net**, not as a versioning product. It is there so a user (or a user through an agent) can look at what a stanza used to be and bring something back. Maps always read the files on disk now. No pins, no per-project frozen revs. Richer uses of history wait until a real need shows up.

A why-log records *why* a stanza changed. It lives in a separate tree so `stanzas/` stays a catalog.

- **Stanza why-log:** `provenance/<id>.md`, same path as the stanza id. Append-only markdown. Written on `create_stanza` and `update_stanza` (and by hand). The stanza file remains the source of truth; the why-log is the rationale. No yaml. No `.prov.md` suffix (the folder is the type).
- **Leftover siblings.** A pre-0.7 `stanzas/<path>/<stem>.prov.md` is not a stanza. The next `update_stanza` or `delete_stanza` migrates or removes it. Do not author new siblings.
- **Not on projects.** v1 has no project why-log. Map edits are attributed in git only. Revisit if binding changes become hard to reconstruct.
- **Frontmatter** `created` / `updated` / `author` on the stanza remain optional metadata, not a substitute for the why-log.

Minimal why-log shape:

```markdown
# Provenance — interaction/how-i-work-with-ai

## 2026-08-16
Why: Split output-style rules out of this stanza so summary-first can stand alone.
```

**Review dial** (configurable; two modes only):

- `auto`: write the files (and the why-log entry) and commit if git is present
- `review`: write or stage; do not commit until the human says yes

Default for every mutation, including `_global` map edits: `review`. Flip the non-global default later if the approval tax gets old.

**Scope:** every mutation, including 0.6 role and project writes and user-gated deletes. One confirm is one git unit, even when a delete touches several maps and frontmatter files. Previews do not touch git. Optional `why` on role and project writes is used only in the git message. There is no role or project why-log file. Map changes alter what gets injected, so they are reviewed writes even without a project why-log.

Default policy lives in `config/review-policy.yaml`:

```yaml
default: review
```

---

## 12. Design Principles

- **Portable** — pure filesystem + optional git. No proprietary formats.
- **Composable** — every stanza is independently reusable.
- **Lean by default** — only `core` stanzas are injected; everything else is on-demand. `_global` stays minimal. Size and token counts are always visible so protocol weight is a managed quantity, not a surprise. Mapped skills still cost host description tokens; keep project `skills:` lists small.
- **Deterministic** — resolution order is explicit and stable; broken references fail loudly; a missing project is a structured miss.
- **Discoverable** — `list_stanzas` is how a user bootstraps a new project's protocol (see what exists, check sizes, then link). The `on_demand` index on a resolved protocol is how an agent pulls extras in-session. Those are different jobs.
- **Weight is visible** — stanza sizes and composed-protocol sizes are first-class authoring data. A protocol that cannot be weighed will grow.
- **Host-injected core:** the composed `core` reaches the agent through files the host already auto-loads. MCP is the live/inspect/authoring surface, not the enforcement path.
- **Agent-native:** designed for MCP-consuming agents, with shipped routers for adoption and `materialize` as the way the pack becomes constitution-grade (and the fallback for environments that cannot use MCP).

---

## 13. Implementer contracts

Locked with review bucket 3 (2026-08-16), plus the 0.4 load-path lock the same day.

- **Token estimate:** `chars / 4` on every size field, labeled an estimate. Relative gauge for authoring, not a model-accurate count.
- **`validate`:** read-only unless `fix=true`.
- **Missing `_global`:** empty global core, vault still resolves.
- **Names and paths:** project keys, stanza path segments, and role ids are `a-z`, `0-9`, `-`. `_global` is the only reserved `_` name. Reject `..`, absolute paths, and anything outside `stanzas/`, `provenance/`, `projects/`, or `roles/`.
- **Git:** safety net for looking back and restoring. Resolution always reads current files. Pinning is not a v1 feature.
- **Vault root:** `INSITU_HOME`, else `--vault`, else `~/.insitu`. One vault per process.
- **`materialize` is the enforcement path.** Always writes `PROTOCOL.md` in the working folder. Writes host adapters only for names in `config/surfaces.yaml`. Missing surfaces file: `PROTOCOL.md` only plus warning `no_surfaces_configured`. Unknown surface name: hard error.
- **Host adapters are full-body copies** at the paths in §10.2. Never write `AGENTS.md`, `CLAUDE.md`, or `CLAUDE.local.md`.
- **Routers are install-time**, user-global, not produced by `materialize`. They must not contain the composed pack. Missing generated protocol: `materialize`. Missing other host files: retrieve the multi-platform pack and write them.
- **Do not gitignore host adapters** that must load. Grok skips gitignored instruction files.
- **Git subprocesses time out.** `rev-parse`, `add`, and `commit` use a bounded timeout. Timeout is a structured miss (`git_timeout` on review; `vault_git_ref` falls back to `none`), not a hung MCP turn.
- **Adapter writes must not deadlock.** If a host adapter is locked or the write does not finish, skip that adapter with `adapter_locked` or `adapter_write_failed`. `PROTOCOL.md` is still written. Prefer CLI `materialize` from a process that does not have those files open.

The 2026-08-16 review buckets are closed. The 0.4 load-path lock is closed.
