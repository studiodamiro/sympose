---
title: "ADR-111 — Drop Target for the Folder Currently in View (amends ADR-110)"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-111 — Drop Target for the Folder Currently in View (amends ADR-110)

- **Status:** Accepted — implemented 2026-09-13, same session as ADR-110.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

damiro tried ADR-110's drag-to-move immediately after it shipped and found a
gap: dragging a note out of a subfolder back up to the root folder it lives
under — e.g. `Code/__scratch/note.md` back to `Code` itself — had nowhere to
land inside the tree panel. `<VaultTree>` only ever renders the *children*
of whichever root folder is currently in view (`AppShell`'s `panelNodes`),
never a row for that root folder itself, so every folder row you could drop
onto was necessarily a level *below* where you started. The only working
route back up was the main-menu's own row for that same folder — reachable,
but off in the sidebar, not where the drag naturally happens.

## Decision

**The folder heading is the missing row.** Every vault panel already
renders an `<h2>` above the tree showing the current folder's name (`Code`,
`Daily`, …) — the one already-visible, always-in-place stand-in for "this
folder" that a `<VaultTree>` row could never be, since the tree itself never
represents its own root. `AppShell`'s heading gained the same
`onDragOver`/`onDragEnter`/`onDragLeave`/`onDrop` wiring as every other drop
target (from ADR-110's `vault-drag.ts` helpers, `isNoteDrag`/`readNoteDrag`)
and calls the same `moveNote(path, activeRootFolder.path)` the main-menu row
already uses — not a new move path, just a second, closer-at-hand way to
reach the one the sidebar already offered. It's gated on `activeRootFolder`
being defined, so it's inert on Settings/Trash/Agent and on a root-level
note (neither has a "folder currently in view" to drop into). The highlight
reuses the exact same `bg-accent/60 ring-1 ring-inset ring-brand/60` treatment
every other drop target uses, so it reads as the same affordance instead of
a one-off.

## Consequences

- Moving a note back up to the root folder it's nested under no longer
  requires leaving the tree panel for the main menu — the always-visible
  folder heading now closes that loop directly above the list.
- No new move logic: this is a third caller of the same `moveNote`
  `AppShell` already had from ADR-110, not a new code path to keep in sync.

## Alternatives rejected

- **Render the current root folder as its own row at the top of the tree.**
  Would also work, but changes what `<VaultTree>` fundamentally renders
  (today strictly the folder's children, ADR-095-era) for every consumer of
  the component, including the bare showcase demo — a much bigger change
  than wiring three more DOM handlers onto an element that already exists
  and already reads as "this folder."
- **Drop anywhere on the empty tree background to mean "move to this
  folder's root."** Rejected — the empty background is often not visible
  (a folder with enough notes fills the panel), so it's not a reliable
  target; the heading is always on-screen regardless of scroll position or
  how full the list is.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 406 passed (backend untouched).
- Manual, in a real browser (disposable test note, fully purged after):
  dragging a note from `Code/__scratch` onto the "Code" heading shows the
  same highlight as every other drop target, fires the same `PATCH
  /api/vault/note` with `new_path: "Code/<name>"`, and the toast/tree
  refresh land exactly as a rename does.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
