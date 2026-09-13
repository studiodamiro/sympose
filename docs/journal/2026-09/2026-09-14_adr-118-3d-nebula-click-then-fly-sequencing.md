---
title: "ADR-118 — 3D Nebula Click-Then-Fly Sequencing (amends ADR-117)"
created: 2026-09-14
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
  - force-graph
---

# ADR-118 — 3D Nebula Click-Then-Fly Sequencing (amends ADR-117)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

With ADR-117's stutter fixed, damiro asked for two things on top: "a bit of
spin" on the camera flight so the 3D renderer's motion reads as distinctly 3D
rather than a flat 2D-style pan/zoom, and — because the colour change and the
camera flight both fired in the same instant — the colour fade (which is what
actually tells you what got clicked) was getting buried under a bigger motion
happening at the same time, reading as an abrupt snap.

Fixing the second one exposed the first as broken:

- **Sequencing.** `handleNodeClick` and the background-click `zoomToFit` path
  both fired the highlight state change and the camera flight synchronously.
  Delaying the flight (`CLICK_ZOOM_LEAD_MS = 220`, via a cancellable
  `scheduleFlyCameraTo`) let the colour fade read on its own first.
- **The flight's easing curve didn't match.** `easeOutQuad` (`t*(2-t)`) has a
  non-zero derivative at `t=0` — the camera jumps to near-max velocity the
  instant the flight starts. Invisible when the camera was already moving
  (the old, un-sequenced behaviour); glaring once there's a still period
  right before it, since a sudden full-speed onset right after stillness
  reads as a second, separate animation kicking in. Switched to
  `easeInOutQuad` so velocity ramps from and back to zero.
- **The controls weren't actually locked during the delay.** `flyCameraTo`
  disabled `enableZoom`/`enableRotate`/`enablePan` only once *it* started
  running — for the whole `CLICK_ZOOM_LEAD_MS` window before that, orbit
  controls were still fully live, so any residual pointer motion right after
  the click could nudge the camera before the flight even began.
  `scheduleFlyCameraTo` now locks the camera down immediately at click time,
  passing the captured `autoRotate` state through to `flyCameraTo` so it can
  still restore it correctly at the end.
- **The spin itself had a real bug, not just a feel problem.** Implemented as
  an orbit angle that decays from `spinDeg` at `t=0` to `0` at `t=1` (so the
  flight lands exactly on the intended framing). But at `t=0` that's the
  *full* spin angle, applied by rotating the camera's actual current position
  around the look-at point immediately — frame one is a discontinuous jump to
  a rotated copy of wherever the camera already was, not a continuation from
  it; the rotation only eases back down to the true starting point as the
  flight proceeds. damiro's own diagnosis, confirmed by a side-by-side test
  (spin on, then isolated off — only removing spin fixed the "frame suddenly
  jerks to a random position, then the animation starts" symptom): "it seems
  like the starting point of the animation is bypassed due to a spin." Fixing
  this properly means easing the remaining angle in *from* 0 at `t=0`
  instead of out *to* 0 at `t=1`. Left at `0` (`CLICK_SPIN_DEG`,
  `BACKGROUND_SPIN_DEG` in `knowledge-nebula-3d.tsx`) rather than re-tuning
  the angle around a still-broken mechanism.

## Decision

Ship the sequencing, easing, and controls-lock fixes — all independently
correct and confirmed. Leave the spin mechanism in the code (distance-scaled,
opposite sign for zoom-in vs. zoom-out) but disabled at `0deg`, with the exact
discontinuity documented at the constant, so a future attempt starts from the
right fix (ease the remaining angle in, not out) instead of re-discovering
this the same way.

## Consequences

- damiro confirmed: "the animation is perfect" with spin at 0.
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.
- Re-enabling spin later requires changing the decay direction in
  `flyCameraTo`'s spin math, not just picking a smaller angle — a smaller
  angle still jumps at `t=0`, just a smaller jump.

## Alternatives rejected

- **Keep spin but shrink the angle further.** Tried (40-50° down to 12-14°)
  before isolating spin entirely — the jump is proportional to the angle but
  present at any non-zero value, so shrinking it only shrinks the symptom,
  it doesn't fix the underlying discontinuity.
- **Remove the spin mechanism entirely instead of disabling it.** It's a
  complete, tested, harmless-at-zero piece of code, not a half-finished
  abstraction — ripping it out would throw away real, working scaffolding
  (distance-scaling, opposite-direction in/out) that the actual bug fix (a
  one-line change to which end of the tween the angle decays from) can reuse
  directly.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
