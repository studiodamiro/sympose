---
title: "ADR-114 — Nebula Force-Graph Mount-Crash Fix & Click-vs-Drag Threshold Recalibration (amends ADR-096, ADR-112)"
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

# ADR-114 — Nebula Force-Graph Mount-Crash Fix & Click-vs-Drag Threshold Recalibration (amends ADR-096, ADR-112)

- **Status:** Accepted, implemented and verified 2026-09-14. Amends ADR-112
  (resolves its "known bug, unresolved" 3D mount-crash) and ADR-096 (the
  pointer-drag threshold that patch introduced was itself still too tight).
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

Two distinct bugs surfaced while damiro verified ADR-112's newly-enabled 3D
toggle against his actual running install (`.venv/bin/python3 app.py
--dashboard`, serving the prebuilt `sympose/webui/` — not the Vite dev server,
a mix-up that cost a couple of debugging round-trips before it was caught).

**Bug 1 — the 3D mount-crash ADR-112 left open.** Confirmed root cause:
`three-forcegraph`'s render loop (`3d-force-graph`'s `_animationCycle`) starts
ticking the instant the kapsule component mounts to its DOM element — which
happens *before* `graphData` has ever been processed, since that only happens
once `react-kapsule` pushes the prop during React's own render pass. The very
first tick reads `state.layout.tick()` while `state.layout` is still
`undefined`, throws, and because `_animationCycle` only calls
`requestAnimationFrame(this._animationCycle)` *after* `tickFrame()` returns,
that one throw kills the render loop permanently — blank stage, forever, no
recovery. Whether a given page load hits this is pure timing luck (does the
first animation frame land before or after `graphData` propagates?), which is
exactly why it looked inconsistent — "works on `/nebula`" one time, blank via
the shell toggle another.

**Bug 2 — clicks and the background-click zoom-out damiro described ("clicking
to a void should zoom out to reveal the whole picture, also unselecting the
selected note") not registering reliably in 3D.** Root cause is *not* a 3D-
specific issue — it is a mis-calibrated fix from ADR-096. That ADR correctly
identified that `force-graph` / `three-render-objects` were short-circuiting
their drag detection to `true` for *any* mouse `pointermove`, and patched it to
gate mouse the same `> 1` px movement-magnitude check touch/pen already used.
But `> 1` device pixel of movement *on a single pointermove event* is still far
tighter than real mouse/trackpad hardware reports during an ordinary,
essentially-still click — confirmed by driving synthetic clicks with
increasing intentional jitter against the patched code: solid through ~3px of
movement, **100% of clicks silently dropped at 5px+**. Since force-graph (2D)
and three-render-objects (3D) share the identical check (same threshold, same
`ev.movementX`/`movementY` pattern), 2D carries the same latent flaw — just
easier to avoid by accident depending on how one happens to click.

## Decision

- **`ui/node_modules/three-forcegraph/dist/three-forcegraph.mjs`
  (`three-forcegraph+1.43.4.patch`, new):** guarded `layoutTick()` with
  `if (!state.layout) return;` at its top. A skipped tick before the
  simulation exists is a pure no-op — there is nothing to position yet — and
  once `_rerender()` assigns `state.layout` on the next commit, ticking
  resumes normally. This is the same treatment ADR-096 already gave two
  sibling libraries in this same dependency family: patch the specific defect
  via `patch-package` rather than working around it from our own component.
- **`ui/node_modules/three-render-objects/dist/three-render-objects.mjs`** and
  **`ui/node_modules/force-graph/dist/force-graph.mjs`** (both patches
  amended): raised the movement-magnitude gate from `> 1` to `> 4`. Chosen
  from the empirical cliff (solid ≤3px, dropped 100% at ≥5px) with headroom;
  confirmed a genuine sustained drag/orbit gesture still clears it immediately
  (a real drag moves far more than 4px on its very first few reported deltas),
  so this doesn't materially weaken drag detection — it only stops flagging an
  ordinary click's natural tremor as one.
- No source-level (`ui/src/`) changes were needed for either fix — both live
  entirely in the vendored, patch-package-managed dependency layer already
  established by ADR-096. `postinstall: patch-package` (existing, generic)
  reapplies all three patches after every `npm install` with no further
  wiring.
- Verified each fix in isolation before combining: the crash-guard alone
  (rebuilt bundle, driven via Playwright) rendered the 3D cloud with zero
  page errors; the threshold change alone (same harness, synthetic clicks at
  0/1/2/3/5/8/10/15px of jitter) dropped 0 of 72 clicks at ≤5px versus 100% at
  5px+ pre-fix, while a 70px sustained drag was still correctly flagged as a
  drag throughout.
- A real, separate gotcha hit mid-session and worth recording: **a Vite dev-
  server restart does not invalidate its dependency pre-bundle cache**
  (`node_modules/.vite/deps`) — that cache is keyed off `package.json`/lockfile
  hashes, not raw `node_modules` file contents, so a `patch-package` edit is
  invisible to an already-running dev server even across a full process
  restart until `node_modules/.vite` is deleted. Compounding this, damiro was
  never on the Vite dev server at all — he runs the packaged build via
  `.venv/bin/python3 app.py --dashboard` (`sympose/webui/`), so several
  restart/verification round-trips chased the wrong process before that
  surfaced. Both gotchas cost real debugging time and are worth remembering
  for the next dependency patch: rebuild `sympose/webui/` and confirm which
  install is actually being tested before trusting a "still broken" report.

## Consequences

- The 3D Knowledge Nebula renderer mounts reliably — no more timing-dependent
  blank stage.
- Node clicks (camera fly-to-cluster, highlight/dim) and background clicks
  (`zoomToFit` + clear selection, matching the exact behavior damiro
  described) now register consistently under realistic mouse/trackpad
  movement, in both 2D and 3D.
- `three-forcegraph+1.43.4.patch` joins `force-graph+1.51.4.patch` and
  `three-render-objects+1.42.0.patch` in `ui/patches/`; the latter two are
  amended in place (same version pin, updated diff) rather than superseded.
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt with all three patches applied — confirmed
  by grepping the built (minified) bundle for the patched constants rather
  than trusting the source-level patch alone.
- ADR-112 is no longer "known bug, unresolved" — both issues raised during its
  own verification are resolved here. A third, independent bug (a duplicate
  background-click dispatch specific to 3D) remained after this fix and is
  resolved separately in ADR-115.

## Alternatives rejected

- **Track cumulative displacement since `pointerdown` instead of raising the
  per-event threshold.** More theoretically correct — an event-by-event
  threshold can in principle be dodged by a very smooth, evenly-spaced slow
  drag where no single step exceeds it, which a synthetic 70px sustained-drag
  test surfaced as a real (if narrow) gap even after this fix. Rejected for
  now: it would mean rewriting the drag-detection mechanism inside two vendor
  libraries rather than recalibrating a constant, is a materially bigger patch
  surface to keep passing `patch-package`'s version-drift guard, and the
  narrow gap it leaves is a synthetic-test artifact (perfectly uniform tiny
  steps) unlikely to occur with real hardware input, which naturally varies in
  speed and timing. Revisit only if a real drag is ever reported as
  registering as a click.
- **Lower the threshold less aggressively (e.g. `> 2`).** The empirical data
  showed a hard cliff at 5px with no partial degradation in between (3px
  clean, 5px 100% dropped), so a smaller bump risked leaving the same problem
  reachable by slightly-more-deliberate real clicks. `> 4` sits with margin on
  the safe side of the observed cliff.
- **Fix the crash from our own component instead of patching the library.**
  Would mean either delaying `graphData` application until after the first
  frame (fights the library's own prop-application timing, fragile) or
  wrapping every call into the imperative handle with defensive checks
  (scattered, easy to miss a call site). A single guard at the actual point of
  failure, inside the already-established patch-package layer, is smaller and
  harder to regress.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
