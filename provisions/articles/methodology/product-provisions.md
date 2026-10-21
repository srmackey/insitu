---
id: methodology/product-provisions
title: Product provisions
description: On install or update of a product checkout, harvest provisions/pack.yaml
  onto the Insitu shelf when present. Generic trigger. No map writes. Skip when the
  provision version did not move.
tags:
- methodology
- insitu
created: '2026-09-16'
updated: '2026-10-21'
---

# Product provisions

When you install or update a **product checkout** in this sitting, look for `provisions/pack.yaml` in that checkout. That file is the public-contract extract list. If it is there, harvest it onto the Insitu shelf. If it is not, continue the product's own install. Do not fail the product install.

This is the trigger. It is generic: install or update of a checkout. Do not name a sibling product's updater.

## Presence

Insitu tools in **this sitting**, not `PROTOCOL.md` on disk.

Call `harvest_provisions` with that checkout as `working_folder`.

- `no_manifest` / `harvested: false`: no public contract to seed. Local product install only.
- `already_present`: provision version unchanged. Skip the Insitu ceremony.
- `first_harvest` true (nothing composes it yet): seed succeeded, **do not write maps**. Name the pack and version in the result. The admin decides subscribe, `_global`, a pin, or leave it on the shelf. Not a new mail type.
- `removed`: leftover shelf versions this call dropped. Expected.
- Refresh plan (`written: false`, `expected.refresh`): confirm with that expected.

Do not write sibling maps. Do not write the install-target map. Available means on the shelf, so a chair that is allowed to subscribe can take it.

## What to copy locally

Internal function always installs in the checkout (the product's own updater).

Public-contract host files: skip only when a map this sitting already loads composes that pack. First harvest still local-installs the public contract unless the admin subscribes in this sitting.

Without Insitu tools, do not call harvest. Install both categories the way the product already installs, into the install-target checkout. Not user-global unless they asked.

## What this is not

Not a pack authoring tool. Not a second copy of the articles. The yaml points at the one home. That home may sit under `provisions/`. A product whose install copies a different tree keeps the files in that tree and points the yaml there.

**Executable.** Tool `harvest_provisions`.

**Class: composition, dependent.** Names the product checkout and the Insitu shelf. The vault does not enforce that declaration.

Reason: a sending chair already has this protocol in memory. The product leaves a file at a known path. Association is that path, not a product-specific command name.
