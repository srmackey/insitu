---
id: methodology/insitu-orientation
title: Insitu orientation
description: What Insitu is, what it holds, and how to look at it. The artifact vocabulary (article, role, pack, skill, map) and the install grains. Link on any map whose agent should know what the vault offers before reaching for it.
tags: [methodology]
created: 2026-08-28
updated: 2026-08-28
---

# Insitu orientation

Insitu is a store of reusable standing guidance. It keeps small pieces of doctrine, composes the ones this project subscribed to into a single protocol, and writes that protocol into this checkout for the host to load.

This article is the vocabulary and the menu. It does not tell you when to author (that is the developer member) and it does not grant permission to work on the vault (that is the admin class).

## What the vault holds

| Object | What it is |
|---|---|
| **Article** | One idea of standing guidance, one file. The atom. Everything else is a way of grouping or delivering articles. |
| **Role** | A named bundle of articles. A convenience for subscribing to several at once. Not permission. |
| **Skill** | A procedure the host exposes as `/name`. Delivered into this checkout as a generated copy. |
| **Pack** | A versioned set of articles, roles, and sometimes skills, authored outside the vault and pulled onto the shelf at `library/<id>/<version>/`. |
| **Map** | This project's subscription: which articles, roles, packs, and skills it takes. One map per project key. |
| **Protocol** | The composed result. Generated, not authored. |

An article is **native** when it lives in this vault, and **from the shelf** when it arrived in a pack. The catalog shows which, so you can tell a local rule from an installed one.

## Two kinds of pack

- A **capability** pack is meant to be taken whole. Subscribing pulls its role, which is the delivery manifest naming what lands in core and what is only indexed, and everything in it.
- A **theme** pack is a menu. Its members are meant to be taken one at a time, and asking for the whole thing is refused (`theme_pack_not_capability`) with the members named, so you can pick.

The pack declares which it is in `pack.yaml`, and the server honours that declaration. Read a pack's INDEX before subscribing anyway: the kind tells you the grain, and the INDEX tells you who each member is for.

## Install grains

Three, from coarse to fine. Match the grain to the pack.

1. **Whole capability.** The pack's role and all its members.
2. **One article.** A single member of a pack, named by pack, version, and article id. This is the grain for theme packs.
3. **One skill.** A single procedure from a pack, mapped so the host exposes it.

Subscriptions pin a version. Two projects may sit on different versions of the same pack, and both stay on the shelf.

## How to look before you reach

Inspect is free and does not change anything. Look first.

- The catalog of articles, with size and origin, so you can see what exists and what it costs.
- One article's body, when you want to read the rule rather than its summary.
- The roles, and what each one bundles.
- The shelf: which packs and versions are present, and which projects use them.
- This project's map, and the composed protocol it produces.

Size is a gauge for authoring, not a verdict. A long article that fires every sitting earns its weight; a short one that never fires does not.

## What stays out

Insitu holds guidance that more than this one project could use, or that this project wants composed for it. It is not a home for project data, notes, status, or work in progress. A rule that only ever applies here can simply live here.

## What this is not

Permission. What a chair may change is an operator class, held in vault config, and it is a separate object from any role or article. Nothing in this article grants a chair the right to alter another project's map.

Provenance: the orientation half of the 0.1.0 creator level, which was dropped in 0.2.0 with the occupancy half. Restored as its own member on 2026-08-28, where it applies to any map.
