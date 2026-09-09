---
title: "ADR-084 — Rename & Delete Notes from the Editor"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-084 — Rename & Delete Notes from the Editor

- **Status:** Accepted — implemented 2026-09-10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Completes note CRUD from the dashboard editor: read (ADR-080),
  save (ADR-081), create (ADR-083), and now rename / delete.

## Context

The editor could open, edit, save, and create notes, but not rename or delete
them — those still meant switching to Obsidian or the shell. The vault manifest
and FTS index also had no removal path: `upsert_note` / `patch_note` only add,
so a deleted file's row lingered until the next mtime-drift rebuild.

## Decision

### Backend — `sympose/vault.py`

- **`_resolve_existing_note(profile, name)`** — the file-resolution tiers
  (`overwrite_note` had inlined) factored into one classmethod, now shared by
  `overwrite_note` / `rename_note` / `delete_note`.
- **`rename_note(profile, old, new)`** — `new` stays in the same folder unless
  it carries a separator. Both ends `is_safe_path`-checked; `NOTE_EXISTS` if the
  target is taken. `os.rename`, then **rewrite every `[[wikilink]]` that
  pointed at the note** (see below). De-index the old path, re-index the new,
  clear the backlink cache.
- **`delete_note(profile, name)`** — move the file to `<vault>/.trash/<relpath>`
  (create the dir; timestamp-suffix on a name clash), then de-index.
  Recoverable, no new dependency, and `.trash` is already in the default
  `ignore_folders` so it stays out of the tree, graph and search.
- **Wikilink rewrite.** `build_backlink_index` already yields the exact set of
  referencing files, so it's a targeted rewrite, not a full-vault walk.
  `_rewrite_wikilink_targets` retargets `[[old]]`, `![[old]]`, `[[old#h]]`,
  `[[old|alias]]` and the `Folder/old` path form to the new stem, leaving
  `#heading` and `|alias` intact. Stem match is exact (`[[alphabet]]` is not
  touched when renaming `alpha`). Each changed file is written back and
  re-indexed.
- Paths are kept as plain `os.path.normpath(join(...))` rather than
  `realpath` — `is_safe_path` resolves symlinks itself, and a `realpath`'d
  target broke `os.path.relpath(dst, mv)` under a symlinked vault root (macOS
  `/var` → `/private/var`). `create_note` carried the same latent bug; fixed
  here too.

### Backend — index / manifest removal

- **`vault_index.remove_note(ws, mv, rel_path)`** — one `DELETE FROM notes`.
- **`vault_manifest.remove_note(ws, mv, rel_path)`** — drop the node and its
  outgoing links; prune bare ids nothing else references. Incoming links from
  other notes are left (they resolve to a ghost — correct for a delete; a
  rename repatches them).

### API — `sympose/server.py`

- **`PATCH /api/vault/note`** `{path, new_path, persona}` → 200 `{path:
  new_path, detail}` / 404 / 409 / 403.
- **`DELETE /api/vault/note?path=&persona=`** → 200 `{detail}` / 404 / 403.

### Frontend

- `renameVaultNote` / `deleteVaultNote` in `vault-note-api.ts`.
- **`<NoteActionsMenu>`** — a `⋯` dropdown overlaid at the right edge of stylo's
  toolbar (its built-ins are left-aligned, so the space is free). *Rename…*
  swaps the button for an inline field prefilled with the filename stem (Enter
  commits, Esc / blur cancels). *Delete…* confirms through a `sonner` toast
  action.
- `MarkdownPanel` gains `onRenamed(newPath)` / `onDeleted()`. The app shell
  points `selectedNote` at the new path (or clears it to the empty state) and
  bumps `vaultRefreshKey` so the tree re-pulls.

## Consequences

- Full note lifecycle from the dashboard — no more round-trips to Obsidian for
  housekeeping.
- Rename touches multiple files (every backlinking note). It is not atomic: if
  the process dies mid-rewrite, the file is renamed but some references are
  not yet updated. Those degrade to ghosts, same as an external rename — the
  next `ensure_fresh` and a re-save fix them. Acceptable for a single-user
  local tool.
- A **bare** `[[old]]` link becomes `[[new]]` — its visible text changes.
  Obsidian would insert `[[new|old]]` to preserve the display; we keep it
  simple and predictable instead. `[[old|alias]]` keeps its alias.
- Delete is recoverable from `<vault>/.trash/` but there is no in-app "restore"
  — you move the file back yourself (or empty `.trash` to purge).
- Path-form links across a folder move (`[[Projects/old]]` when the note leaves
  `Projects/`) keep the stale prefix; they still resolve by stem in Obsidian.
  Same-folder rename — the common case — is exact.

## Alternatives rejected

- **Hard `os.remove` on delete.** Simpler, but unrecoverable unless the vault
  is under git or the OS keeps its own trash. For a vault the user is told is
  sovereign and trustworthy, a recoverable `.trash/` move is the right default.
- **Rename the file only, no wikilink rewrite.** Contained and fast, but every
  `[[old]]` across the vault silently breaks — surprising when the whole point
  of the editor is to work *with* the vault's link graph. Since the backlink
  index makes the rewrite targeted, the cost is low enough to just do it.
- **Dedicated `POST /api/vault/note/rename` + `/delete` endpoints.** More URLs
  for the same resource. `PATCH` (partial update — the name) and `DELETE` are
  the standard verbs; they sit naturally next to the existing `GET` / `PUT` /
  `POST` on `/api/vault/note`.
- **Tree-row context menus for rename/delete.** The Obsidian-native spot, and
  worth adding later, but this pass is editor-scoped per the request. One menu
  in one place first.
- **A confirmation `Dialog` for delete.** Heavier than the action needs; the
  toast action is a single, dismissible, undo-shaped affordance and keeps the
  editor uninterrupted.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
