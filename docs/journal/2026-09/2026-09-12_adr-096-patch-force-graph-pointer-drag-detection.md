---
title: "ADR-096 — Patch force-graph / three-render-objects Pointer-Drag Detection"
created: 2026-09-12
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - nebula
  - dependency
---

# ADR-096 — Patch `force-graph` / `three-render-objects` Pointer-Drag Detection

- **Status:** Accepted — implemented 2026-09-12.
- **Date:** 2026-09-12
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)

## Context

Both Knowledge Nebula renderers intermittently dropped clicks — on a node and
on empty background — with no repeatable trigger from our own code. Traced to
the click-vs-drag disambiguation inside the two upstream rendering libraries:
`force-graph` (2D, `dist/force-graph.mjs`) and `three-render-objects` (the 3D
interaction layer pulled in by `3d-force-graph`, `dist/three-render-objects.mjs`).

Both listen for `pointermove` between `pointerdown` and `pointerup` and flag
the gesture a drag — which silently cancels the pending click entirely,
neither `onNodeClick` nor `onBackgroundClick` fires — using:

```js
(ev.pointerType === 'mouse' || ev.movementX === undefined || [ev.movementX, ev.movementY].some(m => Math.abs(m) > 1))
  && (state.isPointerDragging = true)
```

`ev.pointerType === 'mouse'` short-circuits the whole check to `true` —
meaning for mouse and trackpad input (unlike touch/pen, which correctly go
through the `> 1px` movement-magnitude test), a *single* `pointermove` event
during the press is enough, regardless of actual distance. Real hands aren't
perfectly still for the ~100-200ms of a click; a sub-pixel tremor firing one
`pointermove` is normal and effectively unavoidable. Whether any given click
lands depends on whether the hand happened to twitch at that instant — read
by the user as "clicking a node won't work sometimes" and "clicking to the
void won't take effect sometimes."

Confirmed by reading the exact runtime files Vite bundles (`package.json`
`"module"`/`exports.default"` point at the `.mjs` builds, not the `dist/*.js`
UMD bundles) and confirming the patched logic reaches the shipped
`sympose/webui/` bundle with zero remaining `pointerType === 'mouse'`
occurrences.

## Decision

Patch both libraries with `patch-package` rather than working around it from
our own components:

- **`ui/patches/force-graph+1.51.4.patch`** and
  **`ui/patches/three-render-objects+1.42.0.patch`** — each removes the
  `ev.pointerType === 'mouse' ||` short-circuit so mouse input goes through
  the same `> 1px` movement-magnitude gate touch/pen already use. A comment
  at the patch site explains why, pointing back at the patch file.
- **`patch-package`** added as a `ui/` dev dependency; `"postinstall":
  "patch-package"` in `ui/package.json` reapplies both patches after every
  `npm install`. Verified end-to-end: wiped both packages, reinstalled,
  confirmed `postinstall` reapplied cleanly, then rebuilt and grepped the
  output bundle for the fixed string.

## Consequences

- Node and background clicks in both the 2D and 3D Knowledge Nebula
  renderers now register reliably regardless of ordinary mouse/trackpad
  jitter during the click.
- A dependency upgrade to either package that changes this code region will
  make the patch fail to apply — `patch-package` errors loudly on a failed
  patch rather than silently dropping it, so this surfaces at `npm install`
  time, not as a regression discovered later.
- Two more files for a future contributor to notice in `ui/patches/`; the
  patch's inline comment and this ADR are the trail back to why.

## Alternatives rejected

- **Work around it in our own component code** (intercept pointer events in
  the capture phase ahead of the library's own listeners and swallow
  sub-threshold `pointermove` events before they reach it). No new
  dependency, but delicate event-system code fighting a library's internals
  from the outside — more surface area to get subtly wrong (e.g. also
  suppressing the library's own hover-position tracking for that instant),
  and it doesn't fix the library's raycast-uses-stale-throttled-hover-state
  wrinkle noted below, whereas the drag-flag fix is the actual root cause.
  Rejected once damiro chose "do it properly."
- **Leave it unpatched, document it as a known upstream limitation.** Still
  visibly broken for daily use — this is the app's primary interaction
  surface, not a corner case.
- **Fork and vendor the packages instead of patching.** Heavier to maintain
  than a two-line patch tracked against a specific upstream version;
  `patch-package` already fails loudly on version drift, giving the same
  safety net without owning a full fork.

## Note for a future look

While tracing this, also found (not patched — separate, smaller effect):
`onClick`/`onNodeClick` reads `state.hoverObj`, which is only refreshed by a
throttled raycaster check (`pointerRaycasterThrottleMs`, default 50ms) inside
the render loop rather than a fresh raycast at the moment of the click. Worth
revisiting if clicks still occasionally resolve to the wrong target (or none)
even after this fix.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
