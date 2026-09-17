# Changelog

Notable changes for people using Insitu. Newest first, following [keepachangelog](https://keepachangelog.com).

Insitu is pre-1.0. A minor bump may break callers, and breaking changes are called out under **Changed** and **Removed**.

## [Unreleased]

The first-party public contract (`insitu-core`) now lives in this repo (`articles/`, `skills/`, `provisions/pack.yaml`). Harvest onto the shelf with `harvest_provisions`. Provision version is independent of the server tag.

## [0.24.0] - 2026-09-16

Additive. A product checkout can ship a public-contract extract list. Harvest seeds the shelf without writing maps.

### Added

- **`harvest_provisions`.** On install or update of a checkout, if `provisions/pack.yaml` is present, copy the listed members onto `library/<id>/<version>/` in pack shape. No map change. `first_harvest` is true when nothing composes it yet. `removed` drops unreferenced sibling versions, same as `fetch_pack`. Missing yaml is `harvested: false`, not an error. Same provision version with unchanged bytes is `already_present`. Member lists are `id` plus `path`; a bare id is `extract_list_needs_path`.

## [0.23.0] - 2026-09-11

Additive. The skill catalog now sees the shelf, the same way `list_articles` already did.

### Added

- **`list_skills` includes pack skills on the shelf.** Native rows carry `origin: native`. A skill that exists only under `library/<pack>@<version>` appears with that origin, and `projects` still lists the maps that compose it. Prefix still filters both. `get_skill` without `project` remains native-only.

## [0.22.0] - 2026-09-10

Roles carry skills. A kind of project can subscribe once and get the procedures as well as the articles. Host writing is unchanged: `materialize` still copies the composed skill list into each enabled surface's skills directory.

### Added

- **Role files may list `skills:`.** `create_role` takes `skills=`. `update_role` takes `add_skills` / `remove_skills` under the same preview/confirm gate as article members. `where_used_skill` names role files. `delete_skill` unlinks them.
- **Capability packs deliver role skills.** A whole-capability install expands that version's pack role, skills included. `pack.yaml` `skills:` remains the catalog: a skill listed only there still needs `install_skill`.

### Changed

- Composed skills are `expand(project.roles).skills`, then pack import skills, then map `skills:`. First-wins inside native lists. Native-and-pack collision is still `duplicate_import_skill`.
- `link_skill` and `install_skill` return `already_linked` when the skill is already composed for that project.
- `_global.skills` is still not inherited. Skills on a role that `_global` carries do not fan into other projects.

### Removed

- `role_skills_not_supported`. A `skills` key on a role is membership.

## [0.21.0] - 2026-09-09

Additive for callers that read the new field. Leftover shelf copies of the pack you just seeded go away without a second confirm.

### Added

- **`fetch_pack` returns `removed` and drops unreferenced sibling versions of that pack.** After a successful seed, other on-shelf versions with empty `used_by` are removed in the same call. An exact pin still names its version, so that copy stays. Re-fetch from the pack repo to get a dropped version back. `remove_pack` remains the deliberate delete.

### Changed

- Unreferenced leftover copies of a pack are no longer left on the shelf for someone to notice later. `validate` still reports `unreferenced_version` and still does not delete. `fetch_pack` is the operation that already knew.

## [0.20.0] - 2026-09-08

Additive. Surgical article edits without rewriting the whole body.

### Added

- **`update_article` accepts `old_string` / `new_string`.** Both are required together. The old string must match the body exactly once (`patch_not_found`, `ambiguous_patch`, `incomplete_patch`, `empty_patch`, `conflicting_update` when `content` is also passed). The whole-body `content` path stays. Successful writes return `change` as `patch`, `content`, or `fields`. Why-only calls still return `no_changes`.

## [0.19.0] - 2026-09-05

Additive. Four facts the server already knew at the moment it acted, and did not say.

### Added

- **`fetch_pack` returns `used_by`,** the maps that compose the seeded version, at the grain each takes it. Because every import can pin `latest`, seeding the shelf is the delivery: consumers move without anyone editing a map, and until now the only way to learn who had just received something was to run `list_packs` afterwards and remember to. Both tools now read one computation, so they cannot disagree.
- **`install_article` and `install_skill` warn on a split pin.** Installing from a second version of a pack the map already imports returns `cross_version_pin`, naming the version being added and the ones already there. A warning rather than a refusal, since two rows can be deliberate: a chair may want a skill from a newer version while holding its articles back. The equivalent refusal for the same *article* at two versions (`duplicate_import_article`) already existed one level down; this is the weaker check at the pack level.

- **The four authoring tools warn when provenance is written into the body.** `create_article`, `update_article`, `create_skill`, and `update_skill` scan the body they wrote and return `provenance_in_body` with the line numbers and a pointer to the `why_log` the same call produced. A why-log already has a home outside the composed body; a dated block inside it is a cost every chair holding the provision pays every session, for a fact whose only reader is whoever edits the provision next. A warning rather than a refusal, and anchored at a block opening, so an article whose subject is provenance stays writable. `update_skill` now returns `why_log` as its article counterpart already did, so the pointer resolves there too.

- **`materialize` writes the on-demand index into the generated protocol.** The design has always put an index of a chair's on-demand set on the resolved protocol, but it reached `resolve_protocol`'s result and stopped there, and a result is not what a session holds. The host loads the generated file, so an on-demand article was associated with a chair and unreachable from inside it: knowing when the work calls for one requires knowing the set exists, and nothing put that in front of an agent. `PROTOCOL.md` and every surface adapter now open with an `# On demand` section listing id, estimated cost, and description, no bodies. A chair with an empty list gets no section.

The warning compares the version string a record stores, not a resolved one, so a map whose rows all read `latest` never trips it, and several rows at one version — a capability import beside a skill import — remain the ordinary shape.

## [0.18.0] - 2026-09-04

Additive. A vault with no `classes:` block behaves exactly as it did, and every existing `operators.yaml` loads unchanged.

### Added

- **A class can impose and forbid content, not only grant rights.** `config/operators.yaml` takes an optional `classes:` block where a named class carries `rights`, `obligations` (`core` and `on_demand`), and `prohibitions`. The two rights classes, `admin` and `bound`, are the ladder itself and cannot be redefined by a file.
- **A chair holds a set of classes.** A project's value may be one name or a list. Rights are the union over that set: one `admin` rung anywhere carries the set. `grant` accepts a name or a list and replaces the whole set.
- **Obligations compose without appearing on any map,** ahead of anything the project chose and after `_global`. `include_global: false` does not shed them: opting out of `_global` is a choice, and an obligation is the thing that is not.
- **Prohibitions refuse at a write and exclude at resolution.** `link_article`, `install_article`, and `install_capability` return `prohibited_by_class` and write nothing. `resolve_protocol` instead drops the article and lists it under `excluded`, because a map can acquire a prohibition without its occupant editing anything and failing the resolve would cost that chair its whole protocol.
- **Every surface that explains a composition now names what a class did.** `resolve_protocol` returns `classes`, `imposed`, and `excluded`; `project_status` prints them on its card; the generated protocol header carries a `classes:` line; `where_used` and validate's `unreferenced` count an imposed article as used.
- **`validate` reports `missing_obligation`, `missing_prohibition`, and `obligation_prohibited`.** The first is the sharpest: an obligation naming an article that does not exist fails resolution for every chair in that class at once. Where one held class imposes what another forbids, the prohibition wins in composition and the contradiction is reported.

### Changed

- `operators` returns each project as `{classes, rights}` rather than a single class string, and includes the `classes:` definitions.

## [0.17.0] - 2026-09-04

Stacked on 0.16 and released after it. Additive: nothing that worked before behaves differently unless an article declares a conflict.

### Added

- **`conflicts:` on an article.** An optional list of article ids that must not be composed beside it. The relation is symmetric on read, so one side declaring is enough and an author writes it once.
- **Linking and installing refuse a conflict.** `link_article`, `install_article`, and `install_capability` return `conflicts_with_composed` and write nothing when the arriving article conflicts with one the project already composes, whether that one arrived natively, through a role, or through an import, in core or on-demand. A capability whose own members conflict with each other returns `pack_conflicts_internally`.
- **Resolution warns instead of refusing.** `resolve_protocol` gains a `conflicts` list and still composes. A map pinned to `latest` can receive a conflict from upstream without anyone editing it, and a chair that changed nothing should not lose its protocol.
- **`validate` reports `missing_conflict`** when a declaration names an article that does not exist. Such a declaration reads like a guard and refuses nothing.
- **Installs report what the installed text names.** `install_article`, `install_capability`, and `install_skill` return `mentions_not_composed`: article ids the installed text mentions that this project does not compose, so a companion can be offered at install rather than discovered later. Ids that resolve nowhere are not reported. `install_article` also returns the article's `title` and `description`.

## [0.16.0] - 2026-09-04

Two breaking changes land together so callers absorb one round of edits rather than two.

### Changed

- **The atom is now an article, not a stanza.** Ten tools are renamed: `get_article`, `list_articles`, `create_article`, `update_article`, `delete_article`, `link_article`, `unlink_article`, `install_article`, `uninstall_article`, and `where_used` (unchanged in name, renamed in its argument). Error codes follow (`missing_article`, `article_exists`, `duplicate_import_article`). There are no aliases and no dual-read: the old spelling is gone rather than deprecated.
- **A vault must be migrated before this version can read it.** Rename `stanzas/` to `articles/`, rename the `stanzas:` key to `articles:` inside each map's `imports:` records, and do the same inside any pack version already on the shelf. A pack's own `pack.yaml` uses `articles:` as well.
- **`kind: theme` is now enforced.** `install_capability` against a pack that declares itself a theme is refused with `theme_pack_not_capability` and the response names the members, since a theme pack is a menu whose members are meant to be installed one at a time. Packs that are genuinely taken whole must declare `kind: capability`. Before this version nothing read the field, so check yours.
- Hosts must be restarted after upgrading. Tool names are read at session start, and an already-running session will keep calling the old ones.

### Removed

- **`roles:` on an article.** The field mirrored membership that already lives in the role file, composition never read it, and `validate` could only ever report that the copy had gone stale. `get_role` answers membership from the file that owns it. An existing vault may keep the key; it is ignored on load and never rewritten, so no migration step is required for it.
- **The `role` filter on `list_articles`,** along with the `roles` field on each row. It was the only consumer of the removed field.
- **The `role_membership` finding from `validate`,** and the `fix=true` repair that wrote the mirrored key back.

## [0.15.1] — 2026-08-31

### Fixed

- `materialize` now checks the folder it writes into, not only the chair that called it. Naming one project while pointing at another folder returned success and overwrote that folder's protocol and adapters; where the named project composed no skills, the skill prune also deleted generated skills it found there. A mismatch is now refused with `folder_project_mismatch` and nothing is written, not even the directory.

## [0.15.0] — 2026-08-30

### Added

- All tools declare MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`), so hosts can describe them accurately in permission prompts and directory listings.
- An `operators` reach check on shared vault objects: authoring is open to any chair, while editing or deleting something another project already composes is refused with `shared_object` unless the caller is an admin.

### Changed

- Ten vault-writing tools take a required `working_folder`.
- A composed protocol emits each article's heading from its frontmatter, so an article without one can no longer merge silently into the article above it.

## [0.14.0] — 2026-08-30

### Removed

- **Insitu runs no git commands and has no subprocess surface.** Staging on every mutation, the auto-commit mode, and the commit stamp in generated headers are gone, along with `review` / `staged` / `committed` on every result. Version-controlling a vault is the operator's business.

### Added

- Every mutating tool returns `files`, the vault-relative paths it wrote.

## [0.12] — 2026-08-26

### Added

- Pack-delivered skills install onto a project with `install_skill` / `uninstall_skill`.
- Vault read errors name the file and parse position that failed instead of surfacing a bare parser message.
