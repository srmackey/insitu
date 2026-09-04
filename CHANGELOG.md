# Changelog

Notable changes for people using Insitu. Newest first, following [keepachangelog](https://keepachangelog.com).

Insitu is pre-1.0. A minor bump may break callers, and breaking changes are called out under **Changed** and **Removed**.

## [Unreleased] — 0.18.0

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
