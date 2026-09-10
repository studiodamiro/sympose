---
title: "ADR-085 — Note Recovery: the Vault Trash View"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-085 — Note Recovery: the Vault Trash View

- **Status:** Accepted — implemented 2026-09-10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Closes the loop opened by ADR-084: deletes are recoverable from
  `<vault>/.trash/`, but there was no way back inside the app.

## Context

ADR-084 made `delete_note` move a note to `<vault>/.trash/<relpath>` instead of
unlinking it — recoverable in principle, but only by leaving the dashboard and
moving the file back by hand. `.trash` could also only grow: nothing in the app
listed or cleared it.

ADR-084 also deliberately used a `sonner` toast action to confirm a delete, on
the grounds that a move-to-trash is undo-shaped and a modal would be heavier
than the action needs. That reasoning does not carry over to a **permanent**
delete, which this change introduces.

A review of the ADR-084 destructive paths additionally noted that
`delete_note` computes its `.trash` destination from
`os.path.relpath(src, mv)` and trusts — without asserting — that
`get_allowed_dirs` only ever returns folders under the master vault, so the
relative path can never carry a `..` that would send the trashed copy outside
the vault.

## Decision

### Backend — `sympose/vault_trash.py` (new)

A stdlib-only free-function module, same shape as `vault_index.py` /
`vault_manifest.py`, so `vault.py` does not grow further.

- **`list_trashed(mv, allowed_dirs)`** — walks `<mv>/.trash/**/*.md`, returns
  `{trash_path, original_path, deleted_at (mtime epoch), size}` newest first.
  `original_path` is the trash-relative path with any `delete_note`
  `-YYYYMMDDHHMMSS` clash suffix stripped. Persona-scoped: an entry whose
  original location resolves outside `allowed_dirs` is omitted.
- **`restore(mv, allowed_dirs, trash_rel)`** — both ends `is_safe_path`-checked,
  `makedirs` + `os.rename` back to `original_path`. `TARGET_EXISTS` if something
  occupies that path now; `NOT_IN_TRASH` / `DENIED` otherwise. Prunes the
  now-empty `.trash` sub-directories it leaves behind.
- **`purge(mv, allowed_dirs, trash_rel)`** / **`purge_all(...)`** — the one
  hard-delete path (`os.remove`). Sandbox- and scope-checked.

`VaultManager` gains four thin, sandbox-scoped wrappers — `list_trash`,
`restore_from_trash`, `purge_from_trash`, `empty_trash` — that supply the
persona context, map the module sentinels onto the existing
`NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` vocabulary, and re-index +
re-manifest + clear the backlink cache on a restore (a purge needs none of
that — the file left the index when it was trashed).

### Backend — `delete_note` hardening

`delete_note` now asserts `is_safe_path(dest, mv)` on the computed `.trash`
target before moving anything. Unreachable through the normal
`get_allowed_dirs` invariant, but it makes the guarantee local instead of
inherited from a distance.

### API — `sympose/server.py`

- **`GET /api/vault/trash?persona=`** → `{count, items}`.
- **`POST /api/vault/trash/restore`** `{path, persona}` → 200 `{path, detail}` /
  404 (not in trash) / 409 (original path taken) / 403.
- **`DELETE /api/vault/trash?path=&persona=`** → 200 `{detail}` / 404 / 403.
- **`POST /api/vault/trash/empty`** `{persona}` → 200 `{detail}` / 403.

`restore` is a `POST` sub-resource rather than another verb on
`/api/vault/trash` because it is an action (move back), not a partial update of
the collection; `empty` likewise. Single-note purge stays a plain `DELETE` on
the item.

### Frontend

- **`vault-trash-api.ts`** — `fetchTrash` / `restoreTrashNote` /
  `purgeTrashNote` / `emptyTrash`, same discriminated-result shape as
  `vault-note-api.ts`.
- **`<TrashList>`** — a flat list shown in place of `<VaultTree>` when the vault
  panel's trash toggle (a bin icon beside the new-note icon) is on. Each row:
  original path, "deleted 2h ago", **Restore** and **Delete forever**. A header
  action empties the trash. Owns its own fetch; a `refreshKey` prop lets the
  shell force a re-pull after an outside change (e.g. a fresh delete from the
  editor).
- **`<ConfirmDialog>`** — a controlled yes/no modal on the existing
  `dialog.tsx`. Replaces the ADR-084 `sonner`-toast delete confirm in
  `<NoteActionsMenu>` and `<VaultRowMenu>`, and guards *Delete forever* /
  *Empty trash*. The move-to-trash confirmation goes through the same modal for
  consistency — the toast action button sat one stray click away from a delete.
- The app shell holds the `trashView` toggle and bumps `vaultRefreshKey` when a
  note is restored so the tree picks it back up.

## Consequences

- A deleted note is now fully recoverable without leaving the dashboard, and
  `.trash` no longer only grows — it can be pruned per note or emptied.
- **Permanent deletion is a real, irreversible `os.remove`** — new to the
  product. It is gated behind `<ConfirmDialog>` with an explicit "cannot be
  undone" description, and is persona-scoped (you cannot purge an entry whose
  origin is outside your allowed folders).
- `original_path` recovery is heuristic: a note trashed with a clash suffix
  (`dupe-20260910120000.md`) restores to `dupe.md`. If several same-named notes
  from different folders were trashed, their suffix-stripped paths can collide
  on restore — the second hits `TARGET_EXISTS` and the user renames. Rare, and
  visible rather than silent.
- Restore is not atomic with re-indexing: the file lands first, the index /
  manifest patch is best-effort after. Same tradeoff as every other note op
  here; `ensure_fresh` reconciles on drift.
- The trash listing reads file mtime as the deletion time. `delete_note`
  `os.utime`s the note on the way in so this is accurate on entry; an external
  tool later touching a file inside `.trash`, or a restore-then-redelete, would
  skew the "deleted … ago" label. Cosmetic.

## Alternatives rejected

- **Restore-only, no in-app permanent delete.** Keeps the product free of any
  irreversible action. Rejected: `.trash` then only ever grows, and "empty the
  trash" is a normal expectation of a trash. The irreversibility is contained by
  a real confirm modal.
- **Keep the `sonner`-toast confirm for move-to-trash, add a modal only for
  permanent delete.** Two different confirm affordances for two adjacent
  destructive actions in the same menu. One modal, used for both, is more
  predictable — and supersedes ADR-084's "a Dialog is heavier than the action
  needs", which held only while every delete was recoverable.
- **A dedicated Trash section in the main menu**, like Settings / Account.
  Heavier navigation for a rarely-visited view. A toggle on the vault panel
  header keeps it one context switch away from the tree it complements.
- **A sidecar metadata file per trashed note** (recording exact original path,
  deletion time, deleting persona). Robust against the clash-suffix heuristic,
  but it is state to write, keep consistent, and clean up — and Obsidian would
  show the sidecars. The path-preserving `.trash` layout plus mtime is enough
  for a single-user local tool.
- **`send2trash` / the OS trash.** A new dependency (needs an ADR of its own)
  and it moves notes outside the vault, where the persona and the index can no
  longer see them for recovery. The in-vault `.trash/` stays sovereign.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
