---
title: "ADR-098 — Vault Tree Shows Empty Folders on Disk"
created: 2026-09-12
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-098 — Vault Tree Shows Empty Folders on Disk

- **Status:** Accepted — implemented 2026-09-12.
- **Date:** 2026-09-12
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Amends [ADR-095 — Content Panel Toolbar: Folder Creation & Visit
  History](./2026-09-12_adr-095-content-panel-toolbar-folder-creation-and-visit-history.md).

## Context

damiro created a folder from the content-panel toolbar (ADR-095): the API
call succeeded, the folder existed on disk, but it never appeared in the
dashboard's vault tree — not even after the tree refetch that already runs on
every successful create (`vaultRefreshKey`).

The cause wasn't staleness. `GET /api/vault/tree` builds its `VaultNode` list
by folding the ADR-078 manifest's *note* nodes and synthesizing folder
ancestors from each note's path (`vault_tree.build_tree`,
`sympose/vault_tree.py`). A folder that holds no notes contributes nothing to
that walk, so it never had a way to exist in the tree, no matter how fresh
the manifest was. ADR-095's own consequences section assumed an empty folder
was merely "unindexed until a note lands inside it" — in fact it was
invisible in the UI, full stop.

## Decision

- **`VaultManager._list_real_folders(mv, dirs)`** (`sympose/vault.py`) — a
  directory-only `os.walk` over the persona's allowed dirs (no file reads),
  filtered through the same `vault.ignore_folders` list `_get_vault_snapshot`
  already uses (`.obsidian`, `.git`, `Attachments`, `.trash`, dot-dirs).
  Returns vault-relative directory paths.
- **`vault_tree.build_tree`** takes a new `real_folders` argument and folds
  each path into the tree the same way it already folds a note's folder
  ancestors — reusing the existing `_folder()` container helper, so an
  already-populated folder is a no-op and an empty one gets a bare node with
  no children.
- **`get_vault_tree`** calls `_list_real_folders` and passes it through. No
  change to the ADR-078 manifest schema, no new persisted state, and no
  change needed on delete/rename — the listing is re-derived from disk on
  every call, so it's always correct rather than something to keep in sync.

## Consequences

- A newly created empty folder shows up in the dashboard immediately, on the
  same `vaultRefreshKey` refetch ADR-095 already triggers.
- `GET /api/vault/tree` now does one extra directory-only walk per request.
  Cost scales with folder count (not note count or content), it's off the
  chat/LLM hot path entirely (no TTFT impact), and it's bounded by the same
  ignore list already used elsewhere — so no caching was added for it; a
  cache would need full recursive mtime tracking to stay correct for a
  folder created several levels deep, which is more state than the walk
  itself costs.
- Corrects ADR-095's consequences section, which understated the gap as a
  missing index entry rather than a structural blind spot in a manifest-only
  projection.

## Alternatives rejected

- **Track folders in the ADR-078 manifest itself** (a `folders` list,
  patched in `create_folder`). Keeps the tree purely manifest-driven, but
  now folder create/delete/rename all have to remember to keep that list in
  sync, including the edge case where a tracked-empty folder later gains a
  note. More persisted state for a problem the live walk solves without any.
- **mtime-based caching of the real-folder listing**, mirroring
  `_get_vault_snapshot`'s cache. Rejected because a correct version needs a
  full recursive mtime watermark (a shallow top-level check misses a folder
  created several directories deep, which is exactly the bug being fixed) —
  more complexity than the plain walk it would be saving.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
