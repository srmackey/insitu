# Insitu — Design Spec

**Version 0.16**

Insitu is a portable MCP server for **situated identity**: who you are *here*. This document explains the system as it currently stands. What changed between versions is in `CHANGELOG.md`.

An **article** is a portable section of standing guidance. A **skill** is a procedure the host should expose as `/name`. A **protocol** is the assembled, project-specific "who I am here." The working title during design was Protocol Vault.

---

## 1. Purpose

One vault holds reusable **articles** of standing agent guidance, **roles** that group them, **skills** the host should expose as `/name`, and versioned **packs** a project can install. A **project map** names which of those belong in this folder. `resolve_protocol` composes that set. `materialize` writes the composed core into files the host already injects at session start, plus mapped skill copies under host skill directories.

It solves the common problem of working-with-me guidance being scattered, duplicated, and drifted across projects and hosts (Cursor rules, `AGENTS.md`, `CLAUDE.md`, skill trees, and the rest) by:

- Keeping every reusable article and skill in one vault
- Letting each project declare exactly which articles, roles, packs, and skills belong here
- Writing the composed core and mapped skills into files the host already loads (`materialize`)
- Giving agents `project_status` and `resolve_protocol` to inspect the same composition, `get_article` to pull on-demand pieces, and `get_skill` to inspect a skill body

If the composed pack never sits in the loaded constitution, Insitu is a filing cabinet. Host injection is a kill condition, not a polish item.

The first user is local. The system is structured so someone else could adopt it. It is not an enterprise product.

---

## 2. Scope and boundaries

Insitu owns **user operating context**: who the user is *as it affects how an agent should work with them*, how they want to be worked with, the methodologies and interaction principles they apply across projects, and other durable guidance that belongs in the loaded operating text.

**Inclusion test (host-document test).** A file is an article if you would put it in a Cursor rule, an `AGENTS.md`, or a `CLAUDE.md` so the agent operates differently toward you or the work. Style, method, constraint, and interaction-relevant identity are kinds of content, not different kinds of object. A movie log or a full biography fails the test: that is wiki or primer material.

A **skill** is not an article. Concatenating it into `PROTOCOL.md` would not create a slash command.

Insitu does **not** model engineering or system context: repository knowledge, component ontologies, system facts (auth, security posture, integration quirks), or cross-repo task composition. That is the domain of a dev-context system, and the two are expected to run side by side as separate MCP servers.

Rule of thumb: if it describes *how to work with the user*, it belongs in Insitu; if it describes a *system*, it belongs in the dev-context tool. Gray zone (for example "I prefer pytest"): treat as an article unless it is a fact about a specific repo.

---

## 3. Core concepts

| Concept | Definition |
|---------|----------|
| **Article** | One portable section of standing agent guidance. A markdown file in the vault. Composed into a protocol. |
| **Protocol** | The assembled, project-specific "how to work with me" document. Not an authored source file. Produced by `resolve_protocol` and written by `materialize` to `PROTOCOL.md` plus host adapters. Hosts each have their own name for the equivalent loaded text (rule, constitution, `CLAUDE.md`). |
| **Project** | A named binding that selects which articles make up a protocol. The project key is the directory name under `projects/`. |
| **`_global`** | A distinguished project whose composed core is automatically included in every other project's protocol, unless the project opts out. Keep it very small: only articles that truly transcend projects. |
| **Role** | A named, ordered pack of articles. A project includes a role instead of listing every member. Membership lives in `roles/<id>.yaml` and nowhere else. |
| **Core** | Articles always injected into the protocol. |
| **On-demand** | Articles associated with a project but only loaded when the work needs them (`get_article`). Their titles and descriptions are surfaced on the resolved protocol so agents know what they can pull. |
| **Pack** | Versioned bundle of articles and roles, authored outside the vault. Installed copy lives under `library/<id>/<version>/`. An optional `skills/` folder is copied onto the shelf. |
| **Library** | Vault shelf of pulled pack versions. Not native `articles/`. |
| **Import record** | A project map entry: this node uses a whole **capability** or listed **articles** from a pack id at `version` or `latest`. |
| **Skill** | A procedure the host discovers as `/name`. Vault object under `skills/<id>/SKILL.md`. Membership is `map.yaml` `skills:` only. Roles do not carry skills, and `_global.skills` is not inherited. |

---

## 4. Vault layout

```text
vault/
├── articles/                     # all articles live here
│   ├── interaction/
│   │   ├── summary-first.md
│   │   └── how-i-work-with-ai.md
│   ├── methodology/
│   │   └── ai-system-development.md
│   └── knowledge/
│       └── about-me.md
├── provenance/                   # why-logs; same path as the article id
│   ├── interaction/
│   │   └── summary-first.md
│   └── skills/
│       └── close-books.md
├── skills/                       # first-class skill objects
│   └── close-books/
│       ├── SKILL.md
│       └── scripts/              # optional; copied on materialize
├── roles/                        # named packs
│   ├── clerk.yaml
│   └── steward.yaml
├── projects/
│   ├── _global/
│   │   └── map.yaml
│   └── river-ledger/             # named after the working folder
│       ├── map.yaml
│       └── notes.md              # optional free-form project notes
├── config/
│   ├── surfaces.yaml             # which host adapters materialize writes
│   ├── operators.yaml            # operator classes
│   └── pack-repos.yaml           # optional; zero to many pack repos
└── library/                      # pulled pack versions
    ├── lock.yaml
    └── <pack-id>/<version>/      # mini-vault: articles/, roles/, pack.yaml, VERSION
```

`materialize` writes into the **project checkout** (the working folder), not into the vault:

```text
<working-folder>/
├── PROTOCOL.md                   # portable canon (always written)
├── .grok/rules/insitu-protocol.md
├── .grok/skills/<id>/            # generated copies
├── .claude/rules/insitu-protocol.md
├── .claude/skills/<id>/
├── .cursor/rules/insitu-protocol.mdc
└── .cursor/skills/<id>/
```

Only adapters listed in `config/surfaces.yaml` are written (§10). Install assets (routers, MCP config examples) ship with the **server**, not inside each user's vault (§11).

Folders under `articles/` are a human convention. They are not a type system and do not change load behavior. **Roles** are a type system: they change composition. Do not treat an article folder as a role.

---

## 5. Project identity

The project key **is** the directory name under `projects/`.

**Convention.** The working folder's basename is the project key. Mixed-case folder names fold to lowercase (`ProjectName/` loads `projects/projectname/`). Work in `river-ledger/` and the server loads `projects/river-ledger/`. No extra binding file is required for the common case.

**Labels, not identity.** `map.yaml` may carry `repo`, `name`, and `aka` for display and colloquial lookup. They do not change which project is selected.

**Miss.** If no `projects/<folder>/` exists, `resolve_protocol` returns a structured miss naming the key it tried and the path that was missing. It does not scan the article catalog, and it does not return an empty protocol that looks like success.

**Vault root** is a server concern, not a field on the project map: `INSITU_HOME`, else `--vault`, else `~/.insitu`. One vault per process. A project lives inside a vault; it does not point at one. Pointing the process at another vault is how demos work.

**Charset.** Project keys, article path segments, role ids, pack ids, and skill ids are `a-z`, `0-9`, `-`. Skill ids are a single path segment. `_global` is the only reserved `_` name. Reject `..`, absolute paths, and anything that would escape `articles/`, `provenance/`, `projects/`, `roles/`, `library/`, or `skills/`.

**Not in v1:** a repo-local override file, for a checkout whose folder name is not the project key or a per-repo vault pointer. Add it when a real checkout needs it.

---

## 6. Project map

```yaml
# projects/<folder-name>/map.yaml
repo: river-ledger                # repo identity (label)
name: River Ledger                # optional display name
aka: [rl, riverledger]            # optional colloquial names
roles:                            # optional; ordered role packs
  - clerk
core:                             # ordered; always injected
  - interaction/how-i-work-with-ai
on_demand:                        # associated but not auto-injected
  - knowledge/deep-domain-x
imports:                          # optional; capability / article installs
  - pack: system-development
    version: 0.1.0                # or latest; omit members = whole capability
  # - pack: voices
  #   version: 1.1
  #   articles: [identity/x]      # core members
  #   on_demand: [identity/z]     # indexed, not injected
skills:                           # optional; omit when empty
  - close-books
include_global: true              # optional; default true. Set false to
                                  # exclude _global's composed core.
```

- Order in `roles`, then `imports`, then `core` (and in `_global`) is significant and is preserved in the resolved protocol.
- Paths are relative to the `articles/` directory and use `/` separators.
- `_global` uses the same schema. Its `on_demand` list is normally empty, `include_global` is meaningless there, and it does not need `repo`.
- Free-form project context lives in the optional `notes.md`, not in `map.yaml`.
- There is no `vault:` field on this file.
- A leftover `available:` key is read as `on_demand` and reported as `legacy_available_key`. Both keys on one file is `both_keys_present`. Mutations write `on_demand` only.

### 6.1 Roles

A **role** is a named, ordered pack of articles: how a kind of project carries a shared set of rules without listing every member on every map, and without stuffing `_global`. Roles are vault content, not server builtins; the server has no built-in role names.

**On disk.** One file per role, `roles/<id>.yaml`, the filename stem being the role id. Missing `roles/` is empty.

```yaml
# roles/clerk.yaml
name: Clerk                       # optional display name
description: Receive the inbox; propose cross-project notes upward.
core:
  - methodology/clerk-inbox
on_demand: []                     # optional; default empty
```

- `core` and `on_demand` use the same article-id rules as a project map.
- A role must not list another role. No nesting.
- A role file must not carry a `skills` key (`role_skills_not_supported`).
- Unknown extra fields are ignored on load, though `validate` may warn.

**Membership has one home.** An article does not declare its roles. Membership is a fact about the role file, and an article belongs to it the way a song belongs to a playlist: the playlist knows. Article frontmatter cannot be the membership source, because injection order must be explicit and stable, and because a frontmatter tag would silently enlarge every protocol carrying that article. `get_role` answers membership from the file that owns it. A stale `roles:` key left in an article by an older vault is ignored on load, never read, and never rewritten.

**Project includes.** `map.yaml` `roles:` is an ordered list of role ids. A project may also list articles directly in `core` / `on_demand`. First occurrence wins when the same article appears in a role and again on the map.

**Not a mode.** A role is composition, not a runtime hat. Including a role means those articles are in the protocol. It does not switch behavior sets or change tool privilege.

**`_global` vs roles.** `_global` is the tiny "every project, always" prefix (reply shape, output voice). A role is "every project of this kind." Do not put role behavior on `_global` in order to skip roles. A project that must not receive another kind's rules simply does not include that role.

### 6.2 Packs and the library

Pull, not push. A node **installs** a whole capability, a listed article, or a listed skill at a pack version (`install_capability` / `install_article` / `install_skill`). Insitu resolves `library/<id>/<version>/` first, then `config/pack-repos.yaml` (zero to many; missing or empty is shelf-only). On a hit it copies the pack interior onto the shelf and writes **that** map. On a miss it returns a structured available-versions list, newest first, and does not write the map. Installing never injects into other projects.

User-facing language is "install capability X 1.0," "install identity x at 1.1," "install skill close-hatch at 0.1.0." Not "pin a pack." `fetch_pack` and `remove_pack` are vault admin: seed or delete a shelf version. `update_project` does not pull.

**Pack kind.** A pack declares `kind: capability` or `kind: theme` in `pack.yaml`, and the declaration binds. A capability pack is meant to be taken whole, and its `roles/<pack-id>.yaml` is the delivery manifest. A theme pack is a menu whose members are taken one at a time; `install_capability` against one is refused with `theme_pack_not_capability` and the members are named.

**Shelf.** `library/<pack-id>/<version>/` is a mini-vault (`articles/`, `roles/`, `pack.yaml`, `VERSION`, optional `skills/`). Pack-delivered skills stay on the shelf; `install_skill` maps one id onto this project, and `materialize` writes host copies from that shelf version. A whole-capability install does not attach the pack's skill list. Multiple versions of one id sit side by side, `library/lock.yaml` inventories what is on disk, and native `articles/`, `roles/`, and `skills/` are never merged into.

**Version on a record** is semver (sticky) or `latest` (floats on each resolve and materialize). An exact pin alongside a newer copy composes the pin and reports `newer_available`. Do not auto-upgrade, and do not force other nodes onto a newer version.

**Composition.** `expand(imports)` walks map records in order, resolving `latest` first. A whole capability expands that version's `roles/<pack>.yaml` like a native role. A record's `articles:` are core members and its `on_demand:` are indexed rather than injected. A record's `skills:` compose after native `project.skills`. The same article or skill id arriving from two records on one project is a hard error. Native `roles:` never searches `library/`, and `imports:` never searches vault `roles/`. `get_article` looks in native `articles/` first, then this project's import records at their versions.

**Pack repos** are working copies with one `VERSION`, so a repo query returns that version only. Older versions live on the shelf once pulled.

**Unreferenced versions** — on disk, cited by no map, not the current target of a `latest` — are the finding `unreferenced_version`. `fix` does not delete them; `remove_pack` does, on confirm.

### 6.3 Operator classes

Two classes, stored in `config/operators.yaml` beside `pack-repos.yaml` and `surfaces.yaml`. This is vault state rather than install-folder state, because `INSITU_HOME` moves and the code checkout is shared. It is a discipline gate against casual cross-map writes, not a security boundary: the file is hand-editable by anything with a shell.

```yaml
default_class: bound
projects:
  river-ledger: admin
```

| Class | Mutate maps | Mutate shared objects | `materialize` | Grant / revoke |
|---|---|---|---|---|
| **admin** | any project key | yes | any project, into that project's own checkout | yes |
| **bound** (default) | this project only | only what no other map composes | this folder only | no |

**The calling chair** is the basename of `working_folder`, case-folded. Every mutating map tool requires it, and a bound chair whose key is not `project` gets `chair_bound`. `materialize` takes the same gate; naming no project means this folder's own map, which is always allowed.

**`materialize` reads `working_folder` twice.** For the gate it is the calling chair; for the write it is the destination. A named `project` must match the destination folder's basename, for every class and in a pre-init vault. A mismatch is `folder_project_mismatch`, and nothing is written, not even the folder. This is a check rather than a preference because the project key is *defined* as the folder basename (§5). A sweep names each project's own checkout, so correct usage never meets the refusal.

**Reach, not ownership.** An article, role, or skill belongs to no single map, so binding one to a key would be a category error. What is gated instead is reach: a write that changes what a map other than the calling chair composes is composition authority, and that is admin. The writers of shared objects therefore also take `working_folder`, including `validate` when `fix=true`.

Three consequences follow, and they are the whole rule:

- **Authoring is open to every chair.** `create_*` touches nothing that exists, so it is always allowed. A bound chair writing its own guidance never meets the gate.
- **Editing is open until something else composes it.** An article no map carries, or one only this chair carries, is this chair's to change. The moment a second map composes it, the write is refused with `shared_object`, naming the maps in `used_by`.
- **A role is the sharp case.** Role membership reaches every map carrying that role without touching any of them, which is exactly the change a bound chair should not make alone.

Reach is measured as composition, not as a direct link: an article pulled in through a role counts, and an article on `_global` reaches everything.

**Inspect stays free.** `list_*`, `get_*`, `where_used`, `project_status`, `resolve_protocol`, `operators`, and read-only `validate` may name another project. Vault-store tools (`fetch_pack`, `remove_pack`, pack authoring) stay store-scoped: they write the store, never another project's map.

**Pre-init.** No `operators.yaml` means the vault behaves as it did before classes existed, and every gated result carries a warning naming the fix. Failing closed would lock every chair out of a vault with no admin registered to unlock it. `working_folder` is required either way.

**Bootstrap** is `insitu init --admin <key>` on the command line, guarded to succeed only when no admin exists. It is deliberately not an MCP tool, so an agent cannot claim admin mid-session. Bare `insitu` still starts the server. `grant` and `revoke` are MCP tools that refuse a non-admin caller, and revoking the only admin is refused (`last_admin`).

This is not multi-user ACL.

### 6.4 Validation

`validate` is read-only unless `fix=true`. It checks that every referenced article, role, and skill exists; that ids match paths; that required frontmatter is present; that map entries are not duplicated; and that each exact import record has its version on disk with the listed members present. A broken exact pin is a hard error, as is the same article or skill id arriving from two import records on one project.

**Findings** (`empty_projects`, `empty_roles`, `unreferenced`, `not_in_any_protocol`, `unreferenced_version`, `global_skills_not_inherited`) are authoring hygiene. They never fail `ok`, `fix` never consumes them, and they are not a prompt to delete anything. `fix` applies only safe repairs, on map-local copies; it does not rewrite role files, because that would change every project using the role.

---

## 7. Article format

Articles are Markdown files with YAML frontmatter.

```markdown
---
id: interaction/how-i-work-with-ai
title: How I Work with AI
description: Standing interaction and collaboration preferences
tags: [interaction, core]
created: 2026-08-15
updated: 2026-08-16
---

# How I Work with AI

... content ...
```

- `id` must match the path relative to `articles/`, without `.md`.
- `title` and `description` are **required**. They are surfaced when listing articles and when advertising on-demand articles on a resolved protocol.
- Remaining frontmatter fields are optional but recommended.
- Composition emits the heading from `title`, replacing a leading H1 in the body rather than doubling it. An article therefore cannot be authored so that it merges silently into the text of the one before it.
- Content is ordinary Markdown. An article must not include or transclude another. Composition happens only through project maps and role packs.
- The why-log for an article is `provenance/<id>.md` (§12). It is not itself an article, and listing, validation, and resolution never scan `provenance/`.

---

## 8. Resolution

```
global_composed = expand(_global.roles).core + _global.core       # if _global exists

protocol.core =
    global_composed                 # if include_global
  + expand(project.roles).core
  + expand(project.imports).core
  + project.core

protocol.on_demand =
    expand(project.roles).on_demand
  + expand(project.imports).on_demand
  + project.on_demand
                                    # first-wins dedup throughout
```

`expand(roles)` walks the project's `roles:` list in order and concatenates each role's `core` (or `on_demand`). `include_global` injects `_global`'s **composed** core, roles already expanded, not the raw `_global.core` list. `_global.on_demand` is never pulled into another project.

- **Order is preserved**, and order is injection order. Where guidance conflicts, later entries refine earlier ones: project articles take precedence over roles and imports, and roles over `_global`.
- **Duplicates:** the first occurrence wins and later ones are dropped. `validate` reports them; `fix=true` removes them from map-local copies only.
- **Missing `_global`:** an empty global core. A fresh clone resolves before anyone writes `_global`.
- **Missing `roles/`:** no role packs. A map that names a role then fails.
- **Missing references are a hard error.** A map or role file naming an article, role, or skill that does not exist fails resolution with an error naming the broken reference. Determinism over convenience.
- **An unparseable file is a hard error naming that file.** A malformed article, skill, role, map, lock, pack, or config file fails with its own path and parse position (`VaultReadError`) wherever it is read. Pack trees count: content Insitu did not author still gets named rather than swallowed.
- **Syntax and semantics fail differently.** A file that will not parse raises `VaultReadError`. A file that parses but carries a bad value returns its own structured miss. The first says the file is unreadable, the second says it was read and is wrong.
- **On-demand articles are not in the protocol content.** The resolved protocol carries an **index** of them (id, title, description, size) so the agent knows what it can request via `get_article`.
- **Skills index.** After the on-demand index, `resolve_protocol` lists composed skills (id, name, description, size): native `project.skills`, then pack import skills. No skill content — skill text is never injected into core. A missing skill id is `missing_skill`; a native-and-pack or two-pack collision is `duplicate_import_skill`.
- **Size metadata** comes *before* the core bodies: article count, total bytes, and estimated tokens (`chars / 4`, labeled an estimate), plus the same fields per article, and a separate `skills_size` summary. Size is an authoring surface, not telemetry. A user should be able to see protocol weight and trim it before it bloats every session.
- **Aliases** (`name`, `aka`) do not select a protocol. They are for `list_projects`, and for an agent that heard "RL" and needs to know it means `river-ledger`.

---

## 9. MCP tool surface

| Group | Tools |
|---|---|
| **Compose** | `resolve_protocol` (ordered core, on-demand index, skills index, expanded roles, size totals), `get_article`, `list_on_demand` |
| **Inspect** | `list_articles`, `list_projects`, `get_project`, `project_status`, `list_roles`, `get_role`, `list_skills`, `get_skill`, `list_packs`, `get_pack`, `where_used`, `where_used_skill`, `operators`, `validate` |
| **Article authoring** | `create_article`, `update_article`, `delete_article` |
| **Roles** | `create_role`, `update_role`, `delete_role` |
| **Projects and maps** | `create_project`, `update_project`, `delete_project`, `link_article`, `unlink_article` |
| **Skills** | `create_skill`, `update_skill`, `delete_skill`, `link_skill`, `unlink_skill` |
| **Packs** | `install_capability`, `install_article`, `install_skill`, `uninstall_capability`, `uninstall_article`, `uninstall_skill`, `fetch_pack`, `remove_pack` |
| **Operators** | `grant`, `revoke` |
| **Enforcement** | `materialize` |

`resolve_protocol` is a live inspect tool: weigh the composition, refresh mid-session, compare against a materialized header. It is not how core guidance enters the session (§10). `list_articles` is a bootstrapping and authoring tool — see what exists, check sizes, then link — not agent-session bootstrap. `project_status` is a folder inspect card and never writes.

Native vault skills use `link_skill`; pack skills use `install_skill`. `link_article(..., target="skills")` is `invalid_target`.

**Deletes are user-gated.** `delete_*` and `remove_pack` preview without writing unless `confirm=true` carries the preview's `expected`. Deleting an article unlinks it from role files and maps, then removes the article and its why-log. Deleting a project removes `projects/<key>/` only; articles and roles stay, and `_global` cannot be deleted (`cannot_delete_global`).

**Every write result includes `affects_projects`,** and previews may carry the same list. After an authoring write, if the working-folder basename is in that list, rematerialize and start a new session.

**Every mutating tool takes `working_folder`** (§6.3). Inspect tools do not.

**Every advertised tool declares all four MCP annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`), matched to what its handler does. Reads are read-only and idempotent, `create_*` is not idempotent, `delete_*` and `remove_pack` are destructive, and nothing is open-world: there is no network and no subprocess, and `fetch_pack` resolves from a local path or a configured local source.

There is no `list_protocols` or `get_protocol`. A protocol is not a catalog row. It is what `resolve_protocol` returns and what `materialize` writes.

**Deliberately absent:** search, ACL, `rename_article` / `rename_role` / `rename_project`, nested roles, and role-carried skills. Registering the first admin is not a tool either; it is `insitu init --admin` on the command line.

---

## 10. Materialize: the adapter contract

MCP cannot put text into the system prompt. Only the host can. A constitution line that says "call `resolve_protocol`" is a pull, and a tool result is retrieved text, not standing instruction. Core protocol therefore enters the session through **files the host already auto-loads**, and `materialize` is that path. MCP stays for inspect, on-demand, authoring, and "this header is stale."

Hard rules that must fire even if Insitu is down (privacy, never-fabricate, discretion) stay in the hand-authored constitution. `materialize` never edits those files.

### 10.1 Surfaces config

Which host adapters `materialize` writes is a vault-level fact — which agents this instance actually runs — not a per-project one.

```yaml
# config/surfaces.yaml
surfaces:
  - grok
  - claude
  - cursor
```

Those three names are the known set, and an unknown name is a hard error. If the file is missing, `materialize` writes `PROTOCOL.md` only and returns `no_surfaces_configured`. Existing `.grok/`, `.claude/`, or `.cursor/` trees may be mentioned as a hint in that warning, but they do not cause an adapter to be written. The file is the lock. A work vault and a home vault can list different surfaces.

### 10.2 Outputs

`materialize` always writes `<working-folder>/PROTOCOL.md`. That file is the portable canon: humans read it, adapters derive from it, non-MCP environments consume it. It is **not** auto-loaded by any host, so it is not the injector.

In the same call, for each configured surface, it writes the adapter below. All adapters are **full-body copies** of the composed core plus a generated header. Pointers (`@PROTOCOL.md`) are allowed only where a host expands `@path` at launch, and even there a full body is written so every enabled surface is deterministic without depending on import expansion.

| Surface | Path (under working folder) | Format |
|---------|-----------------------------|--------|
| `grok` | `.grok/rules/insitu-protocol.md` | Full markdown. Grok does not expand `@path` imports, so a body of `@PROTOCOL.md` would inject that string rather than the pack. |
| `claude` | `.claude/rules/insitu-protocol.md` | Full markdown, **no** `paths` frontmatter: a `paths` field would make it on-demand. Rules without `paths` load at launch at the same priority as `CLAUDE.md`. |
| `cursor` | `.cursor/rules/insitu-protocol.mdc` | Full body after YAML frontmatter carrying `alwaysApply: true` and a short description. A plain `.md` in that folder is ignored by Cursor. |

Generated files carry a header (vault root, timestamp, project key, article ids in order) for staleness detection. `materialize` never writes `AGENTS.md`, `CLAUDE.md`, or `CLAUDE.local.md`; a one-line `@PROTOCOL.md` inside an existing `CLAUDE.md` is a human or one-time-install edit.

Do not gitignore host adapters that must load, because Grok skips gitignored instruction files during discovery. Personal or work-unsafe content in a committed adapter is a vault-composition problem — use a work-safe vault or a work-safe `core` — not a gitignore problem.

**Skills.** After the protocol adapters, for each enabled surface and each composed skill, `materialize` writes the allowlisted files (`SKILL.md`, `scripts/`, `references/`) into that surface's skills directory. `SKILL.md` is the vault file with a generated stamp inserted after the closing frontmatter fence; the frontmatter is otherwise byte-identical. It never writes to a user-global skills directory, and never puts skill bodies in `PROTOCOL.md`.

Orphan cleanup is stamp-scoped: under each enabled surface's skills root, a subdirectory whose `SKILL.md` body opens with the Insitu stamp, and whose name is not in the composed skill list, is deleted. Every other directory is left alone.

With no surfaces configured, `PROTOCOL.md` is written alone and no skill directories are touched; a project with a non-empty `skills:` list also gets `skills_need_surfaces`. The result payload reports `skills` and `skills_removed`.

**If an adapter cannot be written** — a locked file, a write that does not finish — that adapter is skipped with `adapter_locked` or `adapter_write_failed`, and `PROTOCOL.md` is still written. Prefer running `materialize` from a process that does not hold those files open.

Regenerate when the vault or the project map changes. A SessionStart hook that runs `materialize` is a freshness helper, not the injector: hosts read rules at session start, so a hook that writes afterward helps the *next* session.

---

## 11. Install and adoption

Two artifacts, different jobs. Do not mix them.

| Artifact | Job | Scope | Written by |
|----------|-----|-------|------------|
| **Router** | Insitu exists; the generated protocol is binding; `get_article` for on-demand; rematerialize when the header is stale | User-global, every project on this machine | Installed once from `install/routers/` |
| **Protocol pack** | The composed `core` text for *this* project | The working folder | `materialize` |

The router is small and almost never changes, and it does not contain the knowledge. The protocol pack is the composed core. A global protocol pack would put the wrong "who I am here" into the wrong tree. Other host files — constitutions, skill trees, this-node bits — are not `materialize` output; when they are missing, the router tells the agent to retrieve them from the multi-platform pack rather than inventing them.

### 11.1 Routers

Routers live in the **server repo** under `install/routers/`, which is their one home, and are copied or symlinked into user-global rule directories. `materialize` does not rewrite them.

| Host | Install destination | Format |
|------|---------------------|--------|
| Cursor | `~/.cursor/rules/insitu-router.mdc` | `alwaysApply: true` |
| Claude | `~/.claude/rules/insitu-router.md` | Markdown, no `paths` |
| Grok | `~/.grok/rules/insitu-router.md` | Markdown |

`install/` also ships MCP config examples and an optional `AGENTS.md` hook snippet: ten lines, insurance, not the injector.

### 11.2 MCP after startup

Once the pack is in the host's auto-load path, agents do not call `resolve_protocol` for core compliance. MCP is then for `project_status`, mid-session inspection and weighing, on-demand pulls, authoring, `validate`, and `where_used`.

One limitation remains. Router-driven tool use — rematerializing on a stale header, pulling an on-demand article — still depends on agent compliance and varies by host. Core load no longer does.

---

## 12. Provenance

A why-log records *why* an article changed. It lives in a separate tree so `articles/` stays a catalog.

- **Article why-log:** `provenance/<id>.md`, the same path as the article id. Append-only markdown, written on create and update, and by hand. The article file remains the source of truth; the why-log is the rationale.
- **Not on projects.** There is no project why-log. Revisit if binding changes become hard to reconstruct.
- **Frontmatter** `created` / `updated` / `author` are optional metadata, not a substitute for the why-log.

```markdown
# Provenance — interaction/how-i-work-with-ai

## 2026-08-16
Why: Split output-style rules out of this article so summary-first can stand alone.
```

**Insitu runs no git commands and has no subprocess surface.** It writes files under the vault root and reports which ones: every mutating tool returns `files`, the vault-relative paths it wrote, and one confirm is one unit — a delete touching several maps reports every path in a single list. Whether the vault is a repository, and what is committed when, belongs to whoever stewards it. Resolution always reads the current files on disk. There are no pins and no per-project frozen revisions.

```json
{"ok": true, "id": "interaction/summary-first",
 "files": ["articles/interaction/summary-first.md",
           "provenance/interaction/summary-first.md"]}
```

---

## 13. Design principles

- **Portable** — plain files on disk, markdown and YAML, no proprietary formats and no database. Insitu runs no git and never shells out; version-controlling a vault is the operator's business.
- **Composable** — composition never depends on which other articles came with it. An article must therefore stand on its own: usable, correct, and safe to follow when composed alone. It may do more when a companion provision is present, and it may name another to contrast with it or to point at the variant a different kind of chair takes. What it may not do is leave the reader following a rule they cannot complete without something they were not given.
- **Lean by default** — only `core` articles are injected; everything else is on-demand, and `_global` stays minimal. Sizes are always visible, so protocol weight is a managed quantity rather than a surprise. Mapped skills still cost host description tokens, so keep `skills:` lists small.
- **Deterministic** — resolution order is explicit and stable, broken references fail loudly, and a missing project is a structured miss.
- **Discoverable** — `list_articles` is how a user bootstraps a new project's protocol; the on-demand index on a resolved protocol is how an agent pulls extras in-session. Different jobs.
- **Weight is visible** — article and composed-protocol sizes are first-class authoring data. A protocol that cannot be weighed will grow.
- **Host-injected core** — the composed core reaches the agent through files the host already auto-loads. MCP is the live, inspect, and authoring surface, not the enforcement path.
- **Agent-native** — designed for MCP-consuming agents, with shipped routers for adoption and `materialize` as the way the pack becomes constitution-grade.
