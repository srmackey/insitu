---
name: tree-card
description: "Write a nested markdown list of this vault's Insitu subscriptions. The project keys are the tree, and each project lists the articles and skills it subscribes to. Use on tree card, or when asked for the subscription tree or for each chair's articles and skills. Writes desk/YYYY-MM-DD-tree-card.md on this chair's checkout."
argument-hint: "tree card"
---

# Tree card

Write one nested markdown list of this vault's Insitu subscriptions. The project keys are the tree. A person scrolls it in an editor.

Triggers: `tree card`, or a request for the subscription tree, or for each chair's articles and skills.

## Where it goes

`desk/YYYY-MM-DD-tree-card.md` on this chair's checkout. The desk is that folder. It is not an overlay path. A second run on the same date replaces the file. The reply names the path and the project count. Do not paste the file.

## Walk

`list_projects` is the set. `_global` is the first item. Every other key is a node. A key's parent is that key with the last segment removed. Parent before its children, in `list_projects` order. A parent key with no project still gets an item, `no subscription`, and its children nest under that item.

Membership is the subscription. The nexus registry is not the walk.

## Each project

`get_project` for the map. `get_role` once per role id, not once per project. `operators` once.

A project other than `_global` with `include_global` gets the line `includes: _global`. Leave `_global`'s articles in that one item.

When `operators` lists the project, add `classes:` with those classes.

Then the subscription, in this order. A role or import that is absent is skipped. An empty articles, on demand, or skills group is left off. A role or import with no members still gets its line. Child chairs come after that chair's own subscription, nested one level deeper. Every chair row is the full project key. Indent is two spaces.

- Each role: its core article ids, then its on-demand ids as `on demand: <id>`, then its skill ids as `skill: <id>`.
- Each import: `pack@version` as the map records it, then that import's article ids and skill ids.
- The map's own `core` articles.
- The map's own `on_demand` ids.
- The map's own `skills`.

## File

```markdown
# Tree card
updated: YYYY-MM-DD

- _global
  - import <pack>@<version>
    - <article id>
  - Articles
    - <id>
- <key>
  - classes: sensitive
  - includes: _global
  - role <id>
    - <article id>
    - on demand: <id>
    - skill: <id>
  - import <pack>@<version>
    - <article id>
    - skill: <id>
  - Articles
    - <id>
  - On demand
    - <id>
  - Skills
    - <id>
  - <child key>
    - includes: _global
```

## Stop

Do not edit a map, materialize, settle, or create a subscription.

**Class: single-system.** Groups with Insitu.
