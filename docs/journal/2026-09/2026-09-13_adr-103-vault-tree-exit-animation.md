---
title: "ADR-103 — Vault-Tree Row Exit Animation on Delete"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-103 — Vault-Tree Row Exit Animation on Delete

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-101/102 gave vault-tree rows an entrance animation
(`animate-in fade-in-0 slide-in-from-left-1 duration-thumb`) for a newly
created note or folder. damiro noticed the asymmetry directly: only the
"show" side animates — deleting a note or folder does not. The `⋯`/right-click
menus already animate closed (Base UI's own `data-closed:animate-out` on
`<DropdownMenuContent>`/`<ContextMenuContent>`), but a deleted vault-tree row
just vanishes: `runDelete`/`runDeleteFolder` (`vault-row-menu.tsx`) call the
delete API, then `onDeleted` bumps `vaultRefreshKey`, the vault tree refetches,
and the next `<VaultTree nodes={…}>` render simply no longer contains that
path — React unmounts the row with no animation, because a plain
`.map(node => <VaultTreeRow key={node.path} …/>)` has nothing to animate
against once the item is gone from the array.

## Decision

**Keep a deleted row mounted for one `duration-thumb` exit animation before
actually dropping it**, via a new hook, `useAnimatedNodeList` (`ui/src/lib/`):
it diffs the incoming `nodes` array against its own `display` state every
render, marks any node that disappeared as `closing: true` instead of
dropping it immediately, and removes it for real only when the caller
reports the animation finished. `VaultTree` calls it on the top-level node
list; `VaultTreeRow` calls it again on its own `node.children` for each
expanded folder — deletion can happen at any depth, and each level of the
tree needs its own closing-row bookkeeping since that's where React's
`.map()`/key-based reconciliation actually happens.

**No fixed exit-duration constant.** The hook doesn't track milliseconds at
all — the row itself drives its own exit with CSS
(`animate-out fade-out-0 slide-out-to-left-1 duration-thumb`, symmetric with
its `animate-in` entrance) and calls back via its own `onAnimationEnd`
DOM event once the animation actually finishes. This was a deliberate
alternative to a `setTimeout(300)` paired with the CSS duration: a JS-side
timer duplicating a value that already lives in CSS is exactly the
"nothing enforced the pairing" problem ADR-101 was written to close, and
`onAnimationEnd` can't drift from whatever the CSS actually does.

A closing row also gets `pointer-events-none` and `aria-hidden` — it's on
its way out and shouldn't be clickable or announced to a screen reader
during the fade.

## A real bug found while building this, fixed in the same change

**`duration-thumb`/`-snappy`/`-mode` only ever set `transition-duration`, not
`--tw-duration`** — the custom property tw-animate-css's `animate-in`/
`animate-out` keyframe utilities actually read
(`animation: … var(--tw-animation-duration, var(--tw-duration, .15s)) …`).
Verified against Tailwind's own built-in numeric `duration-*` utility
(`tailwindcss/dist/lib.js`): it emits *both* `--tw-duration` and
`transition-duration` for exactly this reason. Because the ADR-101/102
tokens only did the latter, every `animate-in`/`animate-out` call site tagged
`duration-thumb` (the vault-tree row entrance, the note-actions/vault-row
`<DropdownMenuContent>`/`<ContextMenuContent>`, the wikilink hover-card) was
silently animating at tw-animate-css's unrelated 150ms default — or, for the
two `<DropdownMenuContent>` sites, the leftover 100ms `--tw-duration` from
`menuPopupClass`'s own `duration-100` that `duration-thumb` never actually
overrode — never the claimed 300ms `<ScrollThumb>`-matched timing ADR-102
documented. `transition-*` properties (`<ScrollThumb>`'s own opacity fade,
menu-item hover colors) were unaffected — the bug was specific to the three
`animate-in`/`animate-out` tiers.

Confirmed with a scratch Playwright check (`getComputedStyle(row)` before and
after, described in §Verification below) — `animationDuration` read `0.15s`
before the fix and `0.3s` after, for the same `duration-thumb` row.

Fixed in `ui/src/index.css` by adding `--tw-duration` to all three
`@utility duration-*` tiers, mirroring Tailwind's own emission order.

## Consequences

- A deleted note or folder row now fades and slides out over the same
  300ms the scrollbar thumb and the row's own entrance use, instead of
  disappearing instantly.
- The `duration-thumb`/`-snappy`/`-mode` fix means every existing
  `animate-in`/`animate-out` call site from ADR-101/102 now actually runs at
  its documented timing — a correctness fix for already-shipped code, not
  just new behavior for this ADR.
- `useAnimatedNodeList` is generic over `VaultNode[]`, not vault-tree-row
  specific — reusable if another mapped, keyed list in the editor/vault
  needs the same "animate the removal" treatment later.

## Alternatives rejected

- **A `setTimeout` matching a hardcoded exit-duration constant** instead of
  `onAnimationEnd`. Rejected: duplicates the CSS duration in JS, exactly the
  drift risk ADR-101 exists to prevent — `onAnimationEnd` reads the real,
  current CSS duration with no second number to keep in sync.
- **A general "exit animation" library** (e.g. `framer-motion`'s
  `AnimatePresence`). Rejected per the zero-bloat/no-new-dependency stance:
  the CSS is already fully in place (`animate-out` and friends, used for
  Base UI's own menu close), the only missing piece was "keep the item
  mounted one beat longer," which a ~50-line hook covers without a new
  runtime dependency.
- **Deferring the actual vault refetch by 300ms** instead of holding a local
  ghost row. Rejected: would delay every *other* row's legitimate update
  (a rename, a new sibling note) by the same 300ms just to let one row
  finish fading, and still wouldn't generalize to a delete nested several
  folders deep without the same per-level bookkeeping `useAnimatedNodeList`
  already does.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- A scratch Playwright check against the `/components` gallery route: a
  temporary local-state button (not committed) removed a mock note from
  the gallery's own `VaultTree` data — no real vault or backend call
  involved — and the script read `getComputedStyle` on the row across three
  checkpoints. Before the `--tw-duration` fix: `animationDuration: "0.15s"`,
  and the row was already gone at the 30ms checkpoint (a second, unrelated
  bug — an infinite `setState`-in-`useEffect` loop from an unmemoized
  `node.children ?? []` fallback recreating a new empty array every render
  for every note row, fixed with a module-level `NO_CHILDREN` constant
  before this check could even complete). After both fixes: `exit`
  animation present at 30ms (`opacity` mid-fade, `animationDuration: "0.3s"`),
  row still present at 230ms, gone by 630ms — matching the intended 300ms
  exit. Screenshotted during development, not checked into either repo.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
