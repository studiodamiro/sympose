---
title: "ADR-112 — Enable the 3D Nebula Renderer in the App Shell (amends ADR-088)"
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

# ADR-112 — Enable the 3D Nebula Renderer in the App Shell (amends ADR-088)

- **Status:** Accepted (amended by ADR-114, which resolves the mount-crash and
  a related click-drop bug both noted below) — amends ADR-088 (Ambient
  Knowledge Nebula in the App Shell, "Phase A"), closing out its deferred
  Phase B item. Implemented 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-088 shipped the app-shell ambient nebula 2D-only, deliberately: `three.js`
stayed out of the persistent background layer's bundle until "the 3D renderer
lands (Phase B)." The 3D renderer itself (`knowledge-nebula-3d.tsx`) had
already existed since 2026-09-01 — full parity with 2D, same shared props/
handle contract — but was only ever reachable through the standalone
`/nebula` showcase route. The app shell's dock (`nebula-controls.tsx`) carried
a `2D | 3D` segmented control with the `3d` segment permanently disabled
(`disabledValues={["3d"]}`) and a "3D renderer lands in a later build" caption.

damiro asked to turn it on and put a settings knob on it — the knob already
existed, cookie-backed (`prefs.mode`), just gated off.

Before flipping it, audited whether 3D had bit-rotted relative to 2D while
gated off. It hadn't in the way expected: every renderer-level fix since
ADR-088 (camera-flight sync, click-zoom, the ADR-096 pointer-drag patch)
landed in the same commits across both `knowledge-nebula-2d.tsx` and
`knowledge-nebula-3d.tsx`, and `AmbientNebula` drives whichever renderer is
active purely through the shared `KnowledgeNebulaHandle`/props contract — so
no renderer-specific shell-integration gap. The one real gap: `autoRotate` was
never wired into the shell dock at all, since only 2D was ever reachable there
(the showcase route has its own separate "Auto Rotate Camera" toggle, 3D-only,
that never got ported over).

## Decision

- **`nebula-controls.tsx`** — dropped `disabledValues={["3d"]}` and the "lands
  in a later build" caption on the Renderer control. Added an `Auto rotate`
  `ToggleRow` to the Display section, shown only when `prefs.mode === "3d"`
  (mirrors the showcase's existing convention for the same knob).
- **`ambient-nebula.tsx`** — was a static, unconditional `KnowledgeNebula2D`
  import. Kept 2D static (still the default, already inside this
  idle-mounted chunk per ADR-088), and added a **nested** `React.lazy` import
  of `KnowledgeNebula3D`, mounted only when `prefs.mode === "3d"`, wrapped in
  its own `<Suspense fallback={null}>`. Both renderers now receive the
  identical prop object (including the newly-added `autoRotate`), so a mode
  switch is a pure swap with no behavior drift between them. This keeps
  ADR-088's own reasoning intact one level deeper: a 2D-only viewer (the
  overwhelming default) still never downloads `three.js`; only someone who
  actually flips to 3D pays for that chunk, and only at that moment rather
  than at idle-mount time.
- **`use-nebula-preferences.ts`** — dropped the stale "3D is Phase B" comment
  on the `mode` knob's default. Default stays `"2d"` — existing users see no
  behavior change until they opt in.
- Verified the code-split held: `npm run build` produces
  `knowledge-nebula-3d-*.js` (~346 KB gzip) as its own chunk, separate from
  `knowledge-nebula-2d-*.js` (~65 KB gzip) and from `index.js`; `2d` mode
  never touches the 3D chunk.

## Consequences

- The `2D | 3D` toggle is live in both the floating dock and Settings →
  Knowledge Nebula (the latter reuses the dock verbatim per ADR-091), cookie-
  persisted, `Auto rotate` alongside it in 3D.
- **Known bug, unresolved:** verifying end-to-end (Playwright against a
  headless Chromium instance, both through the new shell toggle and — to
  isolate this change from any pre-existing issue — directly on the untouched
  `/nebula` showcase route) reproduced an uncaught crash on every 3D mount:
  `three-forcegraph`'s `tickFrame` reads `state.layout.tick()` before
  `state.layout` is assigned by its own `_rerender()`. Because
  `3d-force-graph`'s `_animationCycle` only calls
  `requestAnimationFrame(this._animationCycle)` *after* `tickFrame()`
  returns, the first bad frame throws before the loop reschedules itself —
  the render loop dies permanently and the stage stays blank/black. Confirmed
  this is not a regression from today's change: it reproduces identically on
  the pristine showcase route, and the locked `three-forcegraph` /
  `3d-force-graph` versions (`1.43.4` / `1.80.0`) are byte-identical to the
  original 2026-09-01 commit that introduced 3D — so this looks like a
  dormant race that's simply never been exercised, since 3D has had no live
  path into the product until this change. Caveat: the reproduction
  environment was sandboxed headless Chromium with software WebGL and no live
  backend (vault API calls 502'd, graph fell back to the bundled sample) —
  whether this reproduces under a real GPU-accelerated browser is unconfirmed.
  It did reproduce on damiro's real install and is now fixed — see ADR-114,
  which patches `three-forcegraph`'s mount-order the same way ADR-096 patched
  `force-graph` / `three-render-objects`.
- `.venv/bin/pytest` (406 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.

## Alternatives rejected

- **Statically import both renderers in `ambient-nebula.tsx`.** Simpler — one
  import block instead of a nested lazy boundary — but every 2D-only viewer
  (the default) would download `three.js` inside the already-idle-mounted
  `AmbientNebula` chunk regardless of whether they ever touch 3D. Rejected:
  contradicts ADR-088's own stated reasoning for keeping `three.js` out of
  this layer, just moved one level deeper instead of actually honored.
- **Ship the toggle and declare it done without the crash investigation.**
  damiro's own steer mid-task ("be mindful of the fixes we did on 2d, most
  likely it has the same bugs") made an unverified enable the wrong call —
  ran the actual renderer in a browser instead of trusting a clean `tsc`/
  `vite build`, which is how the crash surfaced at all.
- **Debug and patch the `three-forcegraph` race before reporting back.**
  Would have kept scope creeping into an unbounded third-party-library
  debugging session on a bug whose real-hardware reproducibility is still
  unconfirmed. damiro chose to verify on his own machine first; a patch
  attempt is deferred to a follow-up ADR if he reproduces it.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
