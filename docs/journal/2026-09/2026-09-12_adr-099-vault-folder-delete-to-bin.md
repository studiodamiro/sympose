---
title: "ADR-099 — Vault Folder Delete: Empty Unlinks, Non-Empty Goes to the Bin"
created: 2026-09-12
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-099 — Vault Folder Delete: Empty Unlinks, Non-Empty Goes to the Bin

- **Status:** Accepted — implemented 2026-09-12.
- **Date:** 2026-09-12
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Extends [ADR-095 — Content Panel Toolbar: Folder Creation & Visit
  History](./2026-09-12_adr-095-content-panel-toolbar-folder-creation-and-visit-history.md)
  and [ADR-098 — Vault Tree Shows Empty Folders on
  Disk](./2026-09-12_adr-098-vault-tree-shows-empty-folders.md); reuses the
  `<vault>/.trash/` recoverable-delete contract from
  [ADR-084](./2026-09-10_adr-084-rename-delete-notes-from-editor.md) /
  [ADR-085](./2026-09-10_adr-085-note-recovery-trash-view.md).

## Context

ADR-095/ADR-098 gave folders a create path and made them visible once empty.
The obvious next gap: no way to delete one from the dashboard. The open
question was what happens to whatever is inside — Sympose already treats
note deletion as recoverable (moved to `.trash/`, not unlinked), and folders
should get the same guarantee rather than a second, riskier deletion path.

## Decision

### Backend

- **`VaultManager.delete_folder(profile, folder_name)`** (`sympose/vault.py`)
  resolves the folder the same way `create_folder` does, then branches on
  whether it's empty:
  - **Empty** — nothing to lose, so `os.rmdir` removes it outright. No trash
    round-trip for zero content.
  - **Non-empty** (notes and/or subfolders) — the whole directory moves in
    one `os.rename` to `<vault>/.trash/<same relative path>` — the identical
    move `delete_note` does per-file, just applied to the folder as a unit.
    A name clash in `.trash` gets the same timestamp suffix `delete_note`
    uses. Every note that just moved is then de-indexed individually
    (`vault_index.remove_note` / `vault_manifest.remove_note`) using its
    *original* vault-relative path, so the whole subtree drops out of
    search and the graph while it's parked in the bin.
- **`DELETE /api/vault/folder`** `{path, persona}` (query params, matching
  `DELETE /api/vault/note`) → `200` with the confirmation detail, `404` if
  the path isn't a real folder, `403` outside the sandbox.
- **No changes needed in `vault_trash.py`.** Its list/restore/purge already
  operate file-by-file over whatever sits under `.trash`, regardless of
  whether a note landed there via a single-note delete or a whole-folder
  move — each note that was inside the deleted folder shows up as its own
  independently recoverable row, and restoring one recreates its parent
  folder on the way back (`os.makedirs(..., exist_ok=True)`, already there).

### Frontend

- **`deleteVaultFolder`** (`ui/src/lib/vault-note-api.ts`) — client mirror of
  `deleteVaultNote`.
- **Folder row menu** (`ui/src/components/sympose/vault-row-menu.tsx`) gains
  a destructive "Delete" item alongside the existing "New note here", shared
  by the right-click context menu and the `⋯` dropdown (one `items` list, per
  the house context-menu standard). Behavior branches on the folder node's
  own `children` array (already in hand from the tree, no extra round-trip):
  - **No children** — deletes immediately, no confirmation. Mirrors the
    empty-folder backend path: nothing at risk.
  - **Has children** — asks first via the same `confirm()` helper note
    delete already uses (respecting the user's delete-confirmation
    preference), wording it as deleting the folder "and everything inside
    it," then calls `deleteVaultFolder`.
- **`onDeleted`** in the vault tree's host (`app-shell.tsx`) now also closes
  the editor when the currently open note's path was *nested under* the
  deleted folder (`selectedNote.startsWith(`${path}/`)`), not just an exact
  match — a single callback already shared by both note-row and folder-row
  deletes.

## Consequences

- Folder deletion is recoverable to the same degree note deletion is: an
  empty folder costs nothing to lose, a populated one is fully undoable note
  by note from the Bin.
- The Bin view needs no changes — trashed notes from a deleted folder show up
  as a flat list of individually restorable rows (damiro confirmed this is
  fine; grouping them back under the folder they came from is deferred).
- `_list_real_folders` (ADR-098) naturally reflects a folder's deletion on
  the very next tree fetch — nothing to invalidate, since it re-derives from
  disk every call.

## Alternatives rejected

- **Always trash-move, even for an empty folder.** Adds a round-trip through
  `.trash` for content that never existed — no recoverability benefit, just
  extra directory churn.
- **Refuse to delete a non-empty folder** (`rmdir`-only semantics, forcing
  the user to empty it first). Safer to implement, worse to use — the whole
  point of trashing is that damiro shouldn't have to manually clear a folder
  out note by note before removing it.
- **A "folder" entry type in `vault_trash.py`'s trash listing**, so the Bin
  could show one row per deleted folder instead of one per note. Would need
  new list/restore/purge logic there and a Bin UI change; the flat per-note
  list the existing trash code already produces for free was explicitly
  confirmed as sufficient for now.
- **Recursive de-index in one manifest call** instead of walking the moved
  subtree and calling the existing single-note `remove_note` per file.
  Rejected for the same reason ADR-098 rejected a `folders` manifest list —
  more surface to keep in sync for a walk that's already cheap and already
  proven correct per-file.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
