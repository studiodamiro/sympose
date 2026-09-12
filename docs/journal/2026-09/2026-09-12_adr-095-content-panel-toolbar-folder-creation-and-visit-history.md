---
title: "ADR-095 — Content Panel Toolbar: Folder Creation & Visit History"
created: 2026-09-12
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-095 — Content Panel Toolbar: Folder Creation & Visit History

- **Status:** Accepted — implemented 2026-09-12. Amended by [ADR-098](./2026-09-12_adr-098-vault-tree-shows-empty-folders.md).
- **Date:** 2026-09-12
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Extends [ADR-083 — Editor Note Creation & Frontmatter Round-Trip
  Fidelity](./2026-09-10_adr-083-editor-note-creation-and-frontmatter-fidelity.md),
  which gave the content panel its single inline "New note" action.

## Context

The content panel's header carried one icon button (new note) next to the
folder/section title — everything else about navigating the vault tree went
through the main-menu rail. Two gaps this ADR closes:

1. **No way to create a folder from the dashboard.** Only note files could be
   created; a new folder still required Obsidian or the shell.
2. **No visit history.** Switching between folders/sections (the main-menu
   rail's `active` selection) had no way back to a previously viewed one
   short of re-clicking the rail.

## Decision

### Folder creation

- **`VaultManager.create_folder(profile, folder_name)`** (`sympose/vault.py`)
  — sibling of `create_note`, reusing the same path resolution (master vault
  when the name has a separator, else the persona's primary folder) and the
  same `is_safe_path` sandbox check. `NOTE_EXISTS` when a file or directory
  is already there, `NOTE_DENIED` outside the sandbox. No content to seed —
  it's just `os.makedirs`.
- **`POST /api/vault/folder`** `{path, persona}` → `201` with the confirmation
  detail, `409` if something already exists there, `403` outside the sandbox.
  Behind the same ADR-064.1 password guard as every other vault route.
- **`createVaultFolder`** (`ui/src/lib/vault-note-api.ts`) — client mirror of
  `createVaultNote`.

### Content panel toolbar

- The single "New note" button is replaced with a toolbar row — the same
  `size-7 rounded-md` icon-button treatment the editor toolbar uses
  (`markdown-panel.tsx`) — back/forward on the left, new-note/new-folder on
  the right.
- Both create actions share one piece of state
  (`pendingCreate: "note" | "folder" | null`, `createName`) instead of two
  parallel copies. Clicking either icon toggles an inline text input that
  slides open beside it (`w-0` → `w-40`, `transition-[width]`) rather than
  appearing as a separate full-width row below the header. The input closes
  on blur, `Escape`, or a successful submit.
- **Visit history.** A ref-backed stack + cursor over the rail's `active`
  value, pushed whenever `active` changes (a new pick truncates any forward
  history, matching browser tab-history semantics). Back/forward move the
  cursor and call `setActive` directly, with a guard flag so that
  programmatic move doesn't re-push itself onto the stack. Kept as refs
  (not `useState`) since the stack itself never needs to trigger a render —
  only a small tick counter does, to keep the buttons' `disabled` state
  current.

## Consequences

- Folders and notes can both be created from the dashboard; the vault tree
  no longer requires leaving the app for folder scaffolding.
- The content panel now visually matches the editor toolbar's button
  language, closing a design inconsistency between the two panels.
- Back/forward tracks the *rail's* section history, not a per-note browsing
  history inside a folder — picking a note within a folder (which opens the
  editor) doesn't push a history entry. A note-level "recently viewed" stack
  is a different feature and out of scope here.
- `create_folder` makes no attempt to seed a `.gitkeep`-equivalent or index
  entry — an empty directory is exactly that until a note lands inside it.
  **Correction (ADR-098):** this undersold the actual gap — the dashboard's
  vault tree is a *pure projection of the ADR-078 manifest*, which only ever
  tracks notes, so an empty folder wasn't just unindexed, it was structurally
  invisible in the UI even after a tree refetch. See ADR-098 for the fix.

## Alternatives rejected

- **A `mkdir=true` flag on `POST /api/vault/note`.** Collapses two distinct
  resources (files vs. directories) into one endpoint and one request body,
  the same objection ADR-083 raised against overloading a single verb.
- **Two separate name-input states (`newNoteName`/`newFolderName`,
  `creatingNote`/`creatingFolder`) copy-pasted for folders.** Doubles the
  open/close/blur/keydown wiring for no behavioral difference between the
  two create flows; a single `pendingCreate` discriminator also guarantees
  the two inputs can't both be open at once.
- **A full per-note browsing history (back/forward through every note
  opened in the editor, not just rail sections).** A materially bigger
  feature — it would need to live alongside the editor's own panel state,
  not the content panel's. Deferred until asked for.
- **`useState` for the history stack/cursor.** Every push would be a state
  update on every `active` change purely to re-render two disabled flags;
  refs plus a one-field tick counter avoid re-rendering the stack itself.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
