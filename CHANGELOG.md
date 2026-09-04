# Changelog

Notable changes for people using Insitu. Newest first, following [keepachangelog](https://keepachangelog.com).

Insitu is pre-1.0. A minor bump may break callers, and breaking changes are called out under **Changed** and **Removed**.

## [Unreleased] — 0.16.0

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
