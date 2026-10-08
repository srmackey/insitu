# Tools

Forty-five tools. Each one is the local vault plus, when a call names a folder, that folder. None of them use the network. `openWorldHint` is false on every tool.

The other three hints are one of four sets:

| Kind | readOnlyHint | destructiveHint | idempotentHint |
|---|---|---|---|
| Read | true | false | true |
| Create | false | false | false |
| Write | false | false | true |
| Delete | false | true | true |

Create refuses when the object already exists, so a repeat is not a no-op. Delete previews first and removes the object only when `confirm` is true. Write repeats with the same arguments leave the files as they are.

| Tool | Kind | What it does |
|---|---|---|
| `resolve_protocol` | Read | Return the composed protocol for a project: core bodies, on-demand index, size. Reports conflicts, what a class imposed, and what a class excluded. It never refuses. |
| `get_article` | Read | Return one article by id (path relative to articles/, no .md). Optional project looks through that map's imports. |
| `list_articles` | Read | List articles with title, description, tags, and size. Optional prefix or tag filter. Role membership lives in the role file: use get_role. |
| `list_projects` | Read | List projects including _global, labels, and composed-protocol size summaries. |
| `get_project` | Read | Return a project map, notes, roles, and protocol size summary without the protocol body. |
| `project_status` | Read | Folder inspect card: map, sourced core ids, size, on-demand ids, disk freshness. No article bodies. Inspect only. |
| `list_roles` | Read | List role packs with id, name, description, member counts including skills, and composed core size. |
| `get_role` | Read | Return one role file, member article and skill metadata and sizes, and projects that include it. |
| `list_on_demand` | Read | List on-demand articles associated with a project (id, title, description, size). |
| `list_skills` | Read | List native and shelf skills with origin, size, and which projects compose them. Not session start. |
| `get_skill` | Read | Return one skill: frontmatter, body, size, and payload file list. Optional project looks through that map's pack skills. |
| `where_used_skill` | Read | List project maps and role files that include this skill. |
| `operators` | Read | Inspect: the classes each project holds, what each class imposes and forbids, the registered admins, and the default class. |
| `where_used` | Read | List every project map and role file that references an article. |
| `list_packs` | Read | Shelf inventory: pack ids, versions, which maps use which, unreferenced versions. |
| `get_pack` | Read | One pack id: versions on disk, members, and which maps pin it. |
| `create_article` | Create | Create an article and append a why-log entry. Does not link it to a project. Returns the files written. Authoring is open to any chair. |
| `create_skill` | Create | Create skills/<id>/SKILL.md. Does not auto-link. Optional why writes provenance/skills/<id>.md. |
| `create_role` | Create | Create a role file. The new role is on no project, so authoring is open to any chair. Optional why writes a provenance entry. |
| `create_project` | Create | Create a project map and optional notes. Creating _global when missing is allowed. |
| `validate` | Write | Vault health check. Read-only unless fix=true. Issues fail ok; findings do not. Fixes report the files they wrote and never consume findings. A fix rewrites shared vault files, so it needs admin unless this chair is the only map. |
| `update_article` | Write | Update an article, append a why-log entry, and return where_used. Prefer old_string/new_string for a surgical body edit (exactly one match); content replaces the whole body. |
| `link_skill` | Write | Add a skill to a project's skills list. Writes now. Already composed via a role is already_linked. Does not edit role files. |
| `unlink_skill` | Write | Remove a skill from a project's map. Writes now. |
| `update_skill` | Write | Update SKILL.md frontmatter and/or body. Surfaces where_used and affects_projects. |
| `link_article` | Write | Add an article to a project's core or on-demand list. Does not edit role files. Refused when a class forbids the article, or when it conflicts with one this project already composes. |
| `unlink_article` | Write | Remove an article from a project's map. Does not edit role files. |
| `update_role` | Write | Update a role. Name/description write now. Member add/remove is preview unless confirm=true with the preview's expected. A role reaches every map that carries it, so this needs admin once another map does. |
| `update_project` | Write | Incrementally update a project map. Attach/detach role writes immediately and reports members, weight, and affects_projects. |
| `grant` | Write | Admin only: set the classes a project holds. One name or a list; the set replaces what was there. Rights are the union. |
| `revoke` | Write | Admin only: drop a project back to the default class. Cannot revoke the last admin. |
| `materialize` | Write | Write PROTOCOL.md and configured host adapters into an existing checkout. The folder must already exist. A missing path is working_folder_missing. materialize does not create checkouts. |
| `install_capability` | Write | This project uses the whole pack at version or latest. Pull onto the shelf if needed. Refused on a conflict with what this project composes, or between the pack's own members. |
| `install_article` | Write | This project uses one article from a pack version. Pull onto the shelf if needed. target is core or on_demand. |
| `uninstall_capability` | Write | Drop this map's whole-capability record. Shelf unchanged. |
| `uninstall_article` | Write | Drop this article from this map's import record. Shelf unchanged. |
| `install_skill` | Write | This project uses one skill from a pack version. Pull onto the shelf if needed. Does not copy into native skills/. |
| `uninstall_skill` | Write | Drop this pack skill from this map's import record. Shelf unchanged. |
| `harvest_provisions` | Write | On install or update of a product checkout: if provisions/pack.yaml is present, seed that public contract onto the shelf. No map change. |
| `fetch_pack` | Write | Admin: seed library/<id>/<version>/ from a local path or a configured repo. No map change. Confirm if refreshing changed bytes. |
| `delete_skill` | Delete | Delete a skill. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this skill. |
| `delete_article` | Delete | Delete an article. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this article. |
| `delete_role` | Delete | Delete a role. Preview unless confirm=true with the preview's expected. Do not call unless the user explicitly asked to delete this role. |
| `delete_project` | Delete | Delete a project directory. Preview unless confirm=true with the preview's expected. Cannot delete _global. Do not call unless the user explicitly asked to delete this project. |
| `remove_pack` | Delete | Admin: preview then confirm. Remove a shelf version (or all versions of an id). |

A full sentence for each tool is the docstring on the server. This table keeps the first claim. When a tool is added, removed, or renamed, update this file and `CHANGELOG.md` in the same change.
