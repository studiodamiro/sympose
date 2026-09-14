---
title: "ADR-120 — Click-vs-Drag Detection: Cumulative Displacement Instead of Per-Event Delta (amends ADR-096, ADR-114)"
created: 2026-09-14
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
  - force-graph
  - dependency
---

# ADR-120 — Click-vs-Drag Detection: Cumulative Displacement Instead of Per-Event Delta (amends ADR-096, ADR-114)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

damiro reported clicking empty space in the Knowledge Nebula ("the void")
still missing most of the time, even after ADR-096, ADR-114 and ADR-115. Both
prior rounds patched the same upstream check in `force-graph` (2D) and
`three-render-objects` (3D) — each library flags a click a drag, silently
dropping it (neither `onNodeClick` nor `onBackgroundClick` fires), the moment
a single `pointermove` event during the press reports more than a fixed
pixel threshold of `movementX`/`movementY`. ADR-096 raised that threshold from
the upstream default (effectively 0 for mouse) to `> 1`; ADR-114 found `> 1`
still too tight against real hardware and raised it to `> 4`, backed by
synthetic jitter testing that showed ordinary clicks solid to ~3px and 100%
dropped at 5px+. ADR-115's own Playwright harness, driving 49 jittered clicks
against the `> 4` threshold, still measured 9 genuine misses (~18%) — a
number damiro's real-hardware experience confirms and, by his account, still
undersells.

The remaining flaw isn't the threshold value — it's what's being measured.
`ev.movementX`/`movementY` is the pointer's raw per-event device delta,
reported *before* the OS's pointer-acceleration curve is applied. On a
system with a fast tracking-speed setting, a small, essentially-still hand
movement can still emit an inflated `movementX` on a single event, especially
when the browser coalesces several raw HID reports into one JS-level
`pointermove`. No fixed threshold on that quantity is reliably tunable
against both "reject real jitter" and "accept real drags," because the same
threshold gets hit by both an ordinary click's noise and a small deliberate
drag on high pointer-speed hardware — raising it far enough to fix one
breaks the other. Both libraries already track everything needed for a
better signal: `force-graph` stores the full `pointerdown` event as
`state.pointerDownEvent` (read elsewhere, at the click dispatch); it and
`page{X,Y}` on every subsequent event are already the *accelerated,
on-screen* cursor position, immune to the raw-delta problem entirely.

## Decision

Replace the per-event `movementX`/`movementY` magnitude check with cumulative
on-screen displacement since `pointerdown`, in both patched libraries:

- **`ui/patches/force-graph+1.51.4.patch`** — the drag-detection condition
  now reads `state.pointerDownEvent && Math.hypot(ev.pageX -
  state.pointerDownEvent.pageX, ev.pageY - state.pointerDownEvent.pageY) > 6`,
  replacing the `[movementX, movementY].some(m => Math.abs(m) > 4)` check.
  `state.pointerDownEvent` was already captured on `pointerdown`; nothing new
  to track.
- **`ui/patches/three-render-objects+1.42.0.patch`** — same replacement, but
  this library didn't previously retain the `pointerdown` event, so the
  `pointerdown` branch now also sets `state.pointerDownEvent = ev` (mirroring
  `force-graph`'s existing field name) alongside `state.isPointerPressed`.
- 6px chosen to match the cumulative-distance threshold the old (now-deleted,
  ADR-115) 3D wrapper fallback used for the same job, before it was found to
  race the library's own dispatch — the number itself was never the problem
  with that mechanism, only having two independent dispatch paths was.
- Both hover-freshness fixes from ADR-096 (`flushShadowCanvas()` / resetting
  `lastRaycasterCheck`) are untouched — regenerated via `npx patch-package
  force-graph three-render-objects` from the edited `node_modules`, so they
  carry forward unchanged in the new patch diff.

## Consequences

- Click-vs-drag detection in both Nebula renderers now measures the same
  thing a user actually experiences (on-screen cursor displacement) instead
  of a raw device signal distorted by OS pointer-acceleration settings —
  removing the specific failure mode that made the old check's reliability
  hardware- and settings-dependent.
- Verified: `rm -rf node_modules/force-graph node_modules/three-render-objects
  && npm install` reapplies both regenerated patches cleanly via
  `postinstall`; `npm run typecheck` and `npm run build` clean; grepped the
  built `sympose/webui/` bundle and confirmed the new `pointerDownEvent.pageX`
  check reached both the 2D and 3D chunks with zero remaining `movementX`
  references. `.venv/bin/pytest` — 414 passed.
- A dependency upgrade to either package that changes this code region will
  make the patch fail to apply loudly at `npm install` time, per
  `patch-package`'s existing behavior (unchanged from ADR-096).

## Alternatives rejected

- **Raise the `movementX`/`movementY` threshold again (e.g. to `> 8`).**
  Doesn't fix the actual defect — it's still measuring pre-acceleration
  device delta, so it only shifts where the same failure mode reappears
  (fast-tracking-speed hardware clicking normally vs. slow-tracking-speed
  hardware genuinely dragging a short distance) rather than removing it.
  ADR-114 already tried this once; it bought headroom, not a fix.
- **Re-add a component-level pointerdown/pointerup wrapper tracking
  cumulative distance, as the old 3D fallback did.** Rejected for the same
  reason ADR-115 deleted it: a second dispatch path racing the library's own
  click resolution, not a fix to the library's detection itself. Fixing the
  measurement inside the single existing dispatch path avoids resurrecting
  that race.
- **Fork and vendor the packages instead of patching.** Same reasoning as
  ADR-096: heavier to maintain than a small, loudly-failing patch.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
