---
title: "ADR-119 — 3D Nebula Camera Spin: One-Way Twist on a Random Axis (amends ADR-118)"
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

# ADR-119 — 3D Nebula Camera Spin: One-Way Twist on a Random Axis (amends ADR-118)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-118 shipped the click-driven camera spin at `0deg` after finding it
jumped the camera discontinuously on a flight's very first frame (the spin
angle decayed from full at `t=0` down to `0`, so the full angle applied to
the camera's actual starting position immediately). The first fix tried here
replaced that decay with a `sin(pi * eased)` bump — `0` at both `eased=0` and
`eased=1`, peaking mid-flight — which did remove the jump (confirmed:
screenshots either side of the colour-fade/flight boundary are now pixel
identical). damiro's response: "it spins but when its nearing to its
destination it will revert the spin. so the starting and end looks the
same." Correct — a symmetric bump necessarily returns to the same angle it
started at, so the flight always lands exactly where a straight, spin-free
flight would have; the spin was purely a detour, not a destination change,
and the back half of every flight visibly undid the front half.

Asked directly whether that symmetric behaviour was wanted or whether the
final vantage point should actually differ from the straight-line
destination: damiro chose the latter ("one way twist on random axis angle
rotation"), and separately asked for the rotation axis itself to vary
instead of always being a yaw around world-up.

## Decision

- **One-way twist.** The spin angle now grows monotonically from `0` at
  `t=0` to the full `spinRad` at `t=1` (`spinNow = spinRad * eased`), so it
  persists into the final framing instead of unwinding. The camera still
  ends up the same *distance* from the look-at point — rotation preserves
  the offset vector's length — just arriving from a different angle than a
  straight flight would have.
- **Random rotation axis.** A unit vector uniformly distributed over the
  sphere (via the standard `u = cos(phi)` / `theta` parameterisation, not
  three independent random components then normalised, which biases toward
  cube corners) is drawn once per flight and held fixed for its duration.
  The offset from the look-at point is rotated around this arbitrary axis
  with Rodrigues' rotation formula, rather than the previous 2D rotation
  confined to the X/Z plane (a yaw around world-up only).
- Since the axis is now randomised, a fixed positive/negative sign on
  `spinDeg` no longer meaningfully distinguishes zoom-in from zoom-out (a
  negative angle around a random axis is statistically the same as a
  positive angle around the negated axis) — `CLICK_SPIN_DEG` and
  `BACKGROUND_SPIN_DEG` are now both plain positive magnitudes (25° / 30°).

## Consequences

- Verified via Playwright across three consecutive clicks: no discontinuity
  at the colour-fade/flight boundary in any of them, and each settles at a
  correctly-dimmed, correctly-framed destination.
- damiro confirmed: "nice! perfect!"
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.
- The distance-based spin scaling from ADR-118 (`TRAVEL_FOR_FULL_SPIN`) is
  unchanged and still applies — clicking void again once already at the
  zoomed-out framing still tapers the twist toward negligible rather than
  applying it in place.

## Alternatives rejected

- **Keep the symmetric bump, just make it feel less like an "undo."** Tried
  conceptually but rejected outright once damiro clarified he wanted the
  destination itself to differ, not just a different-shaped detour — no
  amount of re-timing a symmetric curve changes that its start and end
  angles are identical by construction.
- **Keep the axis fixed (world-up) and only fix the one-way growth.** Would
  have addressed the "reverts" complaint but not damiro's explicit follow-up
  ask for the rotation axis itself to vary — every flight would still tumble
  the same way (a yaw), just persisting instead of unwinding.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
