---
title: "ADR-106 — Pinned Notes: Per-Folder Reorder in the Vault Tree"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-106 — Pinned Notes: Per-Folder Reorder in the Vault Tree

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-092 added pin/unpin as local-only prep — a cookie-backed `usePinnedNotes()`
set, a pin glyph on the row, and a Pin/Unpin item in both the vault-row and
editor-toolbar menus — explicitly "ahead of an eventual Pinned/Recent surface."
Pinning did nothing but toggle the glyph. damiro asked to close that gap: group
pinned notes at the top of the list for easy access.

The vault panel's list is `VaultTree` — a nested folder tree, not a flat list —
so "top of the list" needed a scope decision: a vault-wide flat "Pinned"
section above the whole folder tree (matching the `PINNED:`/`RECENT:` pattern
in the mobile design spec's Vault-list and Agent-home artboards), or a
same-level reorder confined to whichever folder a pinned note already lives
in. Put to damiro directly; he chose the latter — the smaller, more
conservative change.

## Decision

**Pinned notes float to the top of their own sibling level, not a separate
cross-vault section.** A pinned note nested three folders deep still requires
opening those folders to reach it; once there, it sorts above its unpinned
siblings (folders and other notes keep their existing relative order below
it).

Implementation lives entirely in `ui/src/components/sympose/vault-tree.tsx`,
no backend involvement:

- A new `sortPinnedFirst()` helper partitions a level's rows into pinned notes
  first, everything else after, and is a no-op when nothing at that level is
  pinned.
- It's applied to `useAnimatedNodeList()`'s **output** (`display`), not its
  input (`nodes`). That hook deliberately keeps every already-mounted row
  pinned to its existing screen position across re-renders — a delete's exit
  animation depends on the rows around it not silently reshuffling — so
  reordering its input would never actually move a row once mounted. Sorting
  the rendered `display` array at both the top level (`VaultTree`) and inside
  each expanded folder (`VaultTreeRow`'s own child list) reorders on every pin
  toggle without touching that hook's add/remove bookkeeping.
- No new persistence: still the same `sympose:vault.pinned` cookie from
  ADR-092, read through the same `isPinned` prop already threaded down to
  `VaultTree`/`VaultTreeRow`.

**"Pinned" caption, styled after the search results caption.** A follow-up
in the same pass: a reorder alone read as an unexplained shuffle, so a small
label now marks where the pinned group starts. `PinnedSectionCaption`
(pin glyph + "Pinned", `text-xs text-fg-muted`) copies the icon-plus-label
treatment `VaultContentSearch` already uses for its "N matches beyond
{folder}" row, so the two groupings read as one visual language rather than
two different conventions. `countLeadingPinned()` reads the already-sorted
`sortPinnedFirst()` output to find where the pinned run ends and renders the
caption only when it's non-empty — at the top of the list and, independently,
at the top of each expanded folder's own child list, matching the per-level
scope of the reorder itself. No caption for "the rest of the list": once the
pinned run ends, unpinned rows simply resume, exactly as damiro asked for.

**"Unpin all" on the caption, and breathing room after the group.** A second
same-day follow-up. The caption gained one action — offered the same two ways
`VaultRowMenu` already offers row actions, for consistency: a hover-revealed
`⋯` button, and right-click / long-press anywhere on the caption line — via
`usePinnedNotes()`'s new `unpinMany(paths)`, a batched sibling to `togglePin`
(one state update and one cookie write instead of `paths.length` sequential
toggles). "Unpin all" is scoped to just that caption's own group — the paths
`countLeadingPinned` found leading that specific level — not a vault-wide
purge, matching the reorder's own per-level scope. A plain spacer (`h-3`,
12px) now sits between the last pinned row and the first unpinned one at each
level, so the reorder doesn't read as an arbitrary shuffle.

## Consequences

- Pinning now visibly does something beyond the row glyph, with zero added
  round-trips or new state — a pure client-side sort of data already in
  memory.
- A vault-wide Pinned/Recent surface (the option damiro didn't pick) is still
  open for later; nothing here forecloses it, since the pin state itself is
  unchanged.
- Finding a pinned note still requires navigating to the folder it lives in —
  the win is not re-scrolling past unpinned siblings once there, not
  eliminating navigation entirely.

## Alternatives rejected

- **Vault-wide flat "Pinned" section above the folder tree.** Recommended
  first as the closer match to the mobile design spec's existing
  `PINNED:`/`RECENT:` grouping convention and the better fit for "easy
  access" on a deeply-nested note. damiro chose the smaller per-folder reorder
  instead.
- **Sorting `useAnimatedNodeList`'s input (`nodes`) instead of its output.**
  Simpler in isolation, but that hook explicitly preserves each existing row's
  display position across re-renders regardless of input order (by design,
  for exit-animation stability), so an input-side reorder would silently fail
  to move any row that was already on screen — only freshly-mounted rows
  would land in the new order.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 398 passed (backend untouched by this change).

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
