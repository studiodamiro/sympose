---
title: "ADR-110 — Drag-and-Drop Note Moves: Vault Tree and Main Menu"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-110 — Drag-and-Drop Note Moves: Vault Tree and Main Menu

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

damiro asked for a faster way to re-file a note than the existing Rename
field (which only ever renames within the same folder — moving meant
retyping a full `Folder/Stem` path into that field by hand). The ask was
scoped in conversation to two drop surfaces: a note row dragged onto another
folder row inside the vault tree currently in view, and a note row dragged
onto a root folder's own entry in the main menu rail. Dragging folders
themselves, and dragging files in/out of the OS (Finder import/export), were
explicitly scoped out — the backend has no folder-move route at all, and an
OS-level drag needs its own path-safety and streaming-upload design, not a
quick follow-on to this.

## Decision

**No new backend route.** `PATCH /api/vault/note` (ADR-084) already
resolves `new_path` under the vault root whenever it carries a `/`, so it
relocates a note across folders exactly as it renames one within a folder —
the only thing missing was a client that called it that way. `moveVaultNote`
(`vault-note-api.ts`) is that client: it joins `destFolder` and the note's
own stem and delegates to the existing `renameVaultNote`. A drop back onto
the note's current folder resolves to `{ ok: true }` without a fetch at all
— caught by comparing `destFolder` against the path's own dirname before
ever calling the endpoint, so a no-op drag costs nothing and can't trip the
backend's own same-path `NOTE_EXISTS` check.

**One drag contract, two drop surfaces.** `vault-drag.ts` is a tiny shared
module: a custom MIME (`application/x-sympose-vault-note-path`), a
`startNoteDrag` for the source, and `isNoteDrag`/`readNoteDrag` for a target.
Using a custom MIME rather than `text/plain` means an OS file drag from
Finder — which carries a `Files` type, never this one — never matches a
drop target meant for an in-app note row, so the out-of-scope OS-import path
can't half-fire.

- `VaultTree` (`vault-tree.tsx`): note rows get `draggable` + `onDragStart`
  whenever the new `onMoveNote` callback is wired — independent of the rest
  of the row-menu gate (`menuReady`), the same way `onTogglePin` is
  independent of it, so a caller can offer drag-to-move without also having
  wired rename/delete/create. Folder rows gain `onDragOver`/`onDrop` behind
  the same check, plus a `dragOver` boolean driving a hover highlight
  (`bg-accent/60` + an inset `ring-brand/60`, the same accent already used
  elsewhere for an active/focused affordance).
- `MainMenu` (`main-menu.tsx`): a new `onDropNote` prop and one
  `dragOverId` piece of state wire the identical drop behavior onto each
  folder item's own row — gated on a new `MainMenuItem.type` field so a
  root-level *note* item (e.g. `README.md`) never becomes a drop target,
  only a folder does. The highlight reuses the same classes as the tree's,
  so a drag reads as one consistent affordance regardless of which rail it
  lands on.
- `AppShell` wires both to one `moveNote(path, destFolder)` function —
  `vaultTreeActions.onMoveNote` and `<MainMenu onDropNote>` both point at it,
  so the tree-drop and menu-drop paths share every line of actual move
  logic (refresh the tree, remap the open note if it was the one moved, and
  the same success/error toast `VaultRowMenu`'s Rename already uses).

**No client-side whitelist duplication.** A drop onto a folder the current
persona can't actually reach still round-trips — `renameVaultNote` surfaces
the backend's existing `NOTE_DENIED` as a normal error toast, same as it
already does for a rename that steps outside the sandbox. Pre-checking each
menu item's own folder-whitelist membership client-side just to grey out an
invalid target would duplicate logic the backend must enforce anyway
(ADR-011/ADR-038) for a case that, in practice, a trusted local dashboard
user rarely hits — not worth the second source of truth for round-trip
frugality's sake.

## Consequences

- Moving a note across folders is now a drag, not a retype-the-whole-path
  rename — including straight onto a different root folder via the main
  menu, which the Rename field alone could never reach without the user
  knowing that folder's exact spelling.
- Zero new backend surface: `PATCH /api/vault/note` gained a client, not a
  route. No new dependency either — native HTML5 drag events, same as every
  other interactive row in the tree.
- A same-folder drop is a genuine no-op: no fetch, no toast, no risk of the
  backend's own `NOTE_EXISTS` guard misfiring on a self-move.
- Folders themselves stay non-draggable — moving a whole folder still has
  no backend route, so no UI pretends otherwise.

## Alternatives rejected

- **A dedicated `POST /api/vault/note/move` route.** Rejected — `PATCH`
  already does this the moment `new_path` carries a folder prefix; a
  parallel route would be a second way to do the same filesystem `rename()`
  for no behavioral gain, just more surface to keep in sync.
- **Pre-computing per-persona valid drop targets to grey out unreachable
  folders.** Rejected for the same reason ADR-011's boundary check already
  lives once, server-side: duplicating the whitelist client-side to avoid
  one occasional error toast isn't worth a second source of truth that can
  drift from the backend's own enforcement.
- **Also making folder rows draggable (move a whole folder by dragging
  it).** Rejected — out of scope for this pass, and there's no backend
  route for it yet (`/api/vault/folder` only creates and deletes); adding
  one is a separate decision with its own subtree-safety questions.
- **OS drag-in/out (Finder <-> Sympose).** Rejected for this pass — needs
  its own design (streamed upload + path-traversal checks for import, the
  browser's native-file-drag API for export) and was explicitly scoped out
  in favor of shipping the cheaper in-app move first.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 406 passed (backend untouched by this change; no new
  route).
- Manual, in a real browser against the running dashboard (a disposable
  test note created and fully purged afterward, vault left exactly as
  found): dragging a note onto a sibling folder inside the vault tree shows
  the hover highlight and lands the note there; dragging a note onto a
  different root folder's main-menu row does the same and the note resolves
  to `<folder>/<name>.md` at that folder's root; dropping a note back onto
  its own folder fires no network call; folder rows carry no `draggable`
  attribute; click-to-open and the row's right-click/`⋯` menu are
  unaffected.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
