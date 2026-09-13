---
title: "ADR-115 — Remove the Duplicate 3D Background-Click Dispatch (amends ADR-112, ADR-114)"
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

# ADR-115 — Remove the Duplicate 3D Background-Click Dispatch (amends ADR-112, ADR-114)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-114 fixed a real 3D mount-crash and a real click-drop threshold, both
confirmed against synthetic tests — but damiro's actual hands-on testing after
both fixes (and a correct app-shell restart, once he was testing against the
right process) still showed the reported symptom, described precisely: click
empty space and an arbitrary node stays highlighted while everything else
dims; click a node and every node lights back up (no highlight) with the
camera flying somewhere unexpected; repeat and the pattern repeats. Not
flaky — reproducible every time, for him.

Rereading `knowledge-nebula-3d.tsx`'s click plumbing end to end explained why:
`onBackgroundClick` was wired **twice**. Once directly to the library —
`<ForceGraph3D onBackgroundClick={onBackgroundClick} onNodeClick={handleNodeClick}>`
— which is reliable on its own now that ADR-096/ADR-114 fixed the library's
click-vs-drag detection. And a second time through this component's own
`handlePointerDown`/`handlePointerUp` pair, tracking cumulative pointer
movement (`< 6px` since `pointerdown`) and, on a 40ms delay, calling
`onBackgroundClick()` itself *unless* a `nodeClickedRef` flag (set inside
`handleNodeClick`) had already flipped true — the exact "dual-fire" the
original 2026-09-01 audit already flagged as an action item and dismissed as
"harmless today, fragile," on the theory that if a node click landed within
40ms, the flag would suppress the redundant fallback.

That theory only holds if the library's own (now-reliable) click dispatch
consistently lands inside that fixed 40ms window. It's asynchronous internally
— ADR-096 documented it as deferred past a fresh hover/raycast pass gated by
`pointerRaycasterThrottleMs` (default 50ms) — so on real hardware, under real
frame timing (unlike the fast, idle headless test environment used to verify
ADR-114), nothing guarantees it beats an arbitrary 40ms constant. Whichever
side lost the race produced exactly what damiro saw: a node click where the
wrapper's own fallback fires first (clearing selection, `zoomToFit`) followed
moments later by the real, correct `onNodeClick` (re-selecting, `flyCameraTo`)
— two independent camera-animation systems (the library's built-in `zoomToFit`
tween and this component's own `flyCameraTo` rAF loop) firing back to back
with nothing to cancel one for the other, which reads exactly as "zooms in,
idk where." And a background click that arrives while an earlier click's
delayed dispatch is still in flight can let that stale dispatch land after the
correct clear, re-selecting whatever node it was — "a random node stays
colored."

**`knowledge-nebula-2d.tsx` has no equivalent mechanism** — it wires
`onNodeClick`/`onBackgroundClick` straight to the library with nothing else
watching pointer state, which is exactly why 2D never exhibited this.

## Decision

Deleted the entire redundant mechanism from `knowledge-nebula-3d.tsx`:
`nodeClickedRef`, `pointerDownPosRef`, `handlePointerDown`, `handlePointerUp`,
and the container div's `onPointerDown`/`onPointerUp` props. `handleNodeClick`
keeps doing exactly what it did before (fly camera to the clicked node's
cluster, call `onNodeClick`), just without also setting the now-deleted flag.
`onBackgroundClick` is passed to `<ForceGraph3D>` alone, matching 2D exactly —
one dispatch path, no race, no 40ms constant to get wrong.

## Consequences

- 3D's click handling is now structurally identical to 2D's: a single,
  direct wire to the library's own (already reliable) `onNodeClick` /
  `onBackgroundClick`.
- Verified with Playwright driving 49 realistic (jittered) clicks across the
  cluster, waiting 500ms after each — long enough for any deferred dispatch —
  and logging every `onNodeClick`/`onBackgroundClick` call: **0 dual-fires**
  (17 clean node hits, 23 clean background hits, 9 genuine misses with no hit
  at all). Before this change the same harness would have shown the
  background fallback firing alongside a real node hit whenever the library's
  dispatch landed outside the 40ms window.
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.
- This is the third and (pending damiro's confirmation on real hardware)
  final fix in the chain that started with ADR-112 enabling 3D: ADR-114 fixed
  a mount-crash and a click-drop threshold; this ADR removes a third,
  independent bug that both of those were necessary but not sufficient to
  surface as fully resolved.

## Alternatives rejected

- **Increase the 40ms delay instead of removing the fallback.** Address the
  symptom (the race window) without removing its cause. The fallback exists
  to catch a background click the library itself supposedly misses — but
  ADR-096 and ADR-114 already made the library's own detection reliable, so
  there's nothing left for the fallback to catch that isn't now *caused* by
  the fallback itself. No delay value is provably safe against a raycast the
  library itself throttles to 50ms by default; removing the second dispatch
  path removes the race instead of re-tuning it.
- **Keep the fallback but gate it on a longer delay matched to
  `pointerRaycasterThrottleMs`.** Ties this component to an internal library
  constant it has no business knowing about, and still leaves two independent
  camera-animation systems (`zoomToFit` vs. `flyCameraTo`) that could
  overlap under different timing. Deleting the redundant path is strictly
  simpler and removes the overlap possibility entirely, not just narrows it.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
