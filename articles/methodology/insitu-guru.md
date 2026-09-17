---
id: methodology/insitu-guru
title: Insitu guru (admin class)
description: Admin-class sitting. Work the vault's shape (catalog, native vs shelf vs maps, group, split, extract) and, on a named charter, sweep listed maps and materialize those checkouts. Link only on a map the vault places in the admin operator class.
tags: [methodology]
created: 2026-08-28
updated: 2026-08-28
---

# Insitu guru (admin class)

This chair may work on the vault itself, not only on its own map. Link this article only on a map that the vault's operator config places in the **admin** class.

An operator class is permission. It is not an Insitu role, and it is not the principal's occupancy. Roles are article bundles. Do not call a class a role.

## The two classes

| Class | Mutate maps | `materialize` | Catalog reconfig | Grant / revoke |
|---|---|---|---|---|
| admin | any listed project | any listed working folder | yes | yes |
| bound (default) | this project only | this folder only | no | no |

`bound` names chair binding: the chair is tied to its own folder and its own key. It is the default, and it is not a lesser rank. Most chairs should stay bound.

Inspect is free to every class. `list_*`, `get_*`, `where_used`, `project_status`, `resolve_protocol`, and read-only `validate` may name another project. Vault-store tools stay store-scoped: they write the store, never another project's map.

## How to follow

1. **Do not assume you are admin.** Read the operator config first. A vault with no config is pre-init: it behaves permissively and says so. Permissive is not a grant. Report that the vault is uninitialized and ask the principal to register an admin from the command line.
2. **The principal names the charter** before any sweep: which map keys, what may change, what is out. Do not invent one, do not widen one, and do not start a sweep because the sitting is going well.
3. **Work the shape, not the contents.** Read the catalog: what is native to this vault, what came off the shelf, which maps carry it. Group what repeats, split what carries two ideas, extract what another map would reuse. One idea per article.
4. **A pack member's home is its pack.** Edit it in the pack-authoring chair and bump that pack's version. Do not patch an installed copy and treat it as the source.
5. **Sweep, then say it is stale.** After mutating the listed maps, `materialize` each listed checkout in the same sitting. Then tell the user those sessions are running an old protocol and should be restarted.
6. **Never node data.** `materialize` writes the composed protocol and the host adapters. It does not write constitutions, inbox, status, board, or privacy files. A finding is not a delete prompt.
7. **Grant and revoke are deliberate.** Only admin may change a map's class, and the change goes through the vault's operator config. Registering the first admin is a command-line step outside the session, so a sitting cannot promote itself.

## Map hygiene

A project map exists because that project subscribed, and it goes when the project uninstalls or its checkout is gone. The vault does not mirror an external roster. Membership in some other registry, or a config file sitting in a folder, does not imply a subscription.

The create half enforces itself, since a map only appears by subscribing. The remove half does not: nothing detects an orphaned map today. When you are in the catalog, look for maps whose checkout no longer exists and raise them. Do not delete on your own.

## What this is not

Occupancy. How the principal sits is a different object, and this article does not grant it.

A security boundary. The operator config is a local file, and anything with a shell can edit it. This is a discipline gate against casual cross-map writes, not access control.

Provenance: Insitu operator classes, recorded 2026-08-26, scope settled 2026-08-28. Instruction ships before the server refuse; until that lands, this article is the rule.
