---
title: "ADR-117 — 3D Nebula Click Stutter: Three Independent Root Causes (amends ADR-112, ADR-116)"
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

# ADR-117 — 3D Nebula Click Stutter: Three Independent Root Causes (amends ADR-112, ADR-116)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

After ADR-116 fixed the 3D highlight/dim never reaching the screen, damiro
reported the whole app felt jerky whenever the nebula was animating, and
separately that clicking a node worked but "the animation is off." Chasing
this down turned up three unrelated problems stacked on top of each other,
each independently real:

1. **Continuous forced rotation.** `shouldRotate = autoRotate || dimmed` (from
   the original 3D renderer commit, predating this session) auto-orbits the
   camera any time the nebula is merely dimmed — i.e. all the time, in
   ordinary Focus mode, contradicting the component's own doc comment that
   Focus is "dimmed and inert." This ran a `requestAnimationFrame` loop
   forever, forcing a full scene redraw every frame regardless of whether
   anything else was happening.
2. **Unstable accessor identities forcing full rebuilds.** `nodeColor`,
   `nodeVal`, `nodeVisibility`, `linkColor`, `linkWidth`, and `linkVisibility`
   were all inline arrow functions defined fresh on every render of
   `KnowledgeNebula3D`. `three-forcegraph`'s `hasAnyPropChanged` treats a
   changed function *reference* as "the data changed" and reruns a full
   node/link material digest in response — so every click (which changes
   `highlightedNodeIds` and re-renders the component) was triggering a full
   rebuild of every node's and every link's material, on top of whatever
   ADR-116's `fg.refresh()` was already doing.
3. **The `fg.refresh()` fix itself was expensive at native frame rates.**
   Confirmed by direct timing: cheap in isolation, but since colours ease
   continuously, virtually every node differs from its last-drawn colour on
   virtually every frame — so calling `refresh()` (which walks every node and
   link and rebuilds any material that differs) once per animation frame for
   the ~15-20 frames a fade takes was rebuilding ~900+ materials from scratch
   up to 60 times a second. A time-based throttle on the refresh cadence made
   it marginally better, but each still-heavy call remained a visible hitch —
   just a sparser one.

## Decision

- **Stop forcing rotation while merely dimmed.** `shouldRotate` is now just
  `autoRotate` — the explicit user toggle, not an implicit side effect of
  Focus mode.
- **Give every dynamic `<ForceGraph3D>` accessor a stable identity.**
  `nodeVisibilityFn`, `linkVisibilityFn`, `nodeValFn`, `nodeColorFn`,
  `linkColorFn`, and `linkWidthFn` are now `useCallback(..., [])`, reading
  live values through the same ref-mirroring pattern the file already used
  for its label-fade loop (`highlightedIdsRef`, `hiddenIdsRef`, `isLightRef`,
  new `nodeSeparationRef`/`nodeVividnessRef`/`activeLinkWidthRef`). A re-render
  no longer implicitly triggers a full digest — only an explicit refresh does.
- **Bypass the library's digest for colour entirely.** Instead of mutating
  `__highlightT` and calling `fg.refresh()` to make the library rebuild
  materials, each node's default sphere mesh (`node.__threeObj`) has its
  material cloned once (so it's never shared with another node sitting at the
  same resting colour — three-forcegraph's own digest deliberately shares one
  material instance across same-colour nodes) and from then on the rAF loop
  writes `.color`/`.opacity` on that private material directly. That's a
  couple of cheap property writes per node, no allocation once cloned, no
  digest, and three.js picks it up on its next render for free — no
  `fg.refresh()` call needed at all any more. The loop also now skips nodes
  that are already settled *and* already own a private material, so the cost
  is proportional to how many nodes are actually mid-fade, not the whole
  graph, forever.

## Consequences

- Verified via Playwright: dim/highlight and full-colour restore both still
  land on the exact correct final state after this rewrite; Focus-mode frames
  2s apart are now pixel-identical (no more forced ambient rotation).
- damiro confirmed the click/deselect stutter is gone after this change.
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.
- This landed in `origin/main` under an unrelated, already-pushed commit
  (`098e509`, about the vault-tree row-menu gutter) due to a `git stash`
  mix-up during this same session — a correctly-labelled follow-up commit
  (`cf0925d`) documents and completes it rather than rewriting that history.

## Alternatives rejected

- **Throttle `fg.refresh()`'s call rate instead of bypassing it.** Tried
  first (~12 flushes/sec instead of 60). Reduced total work but each
  individual call was still a full-graph digest, so repeated clicks still
  produced a countable number of visible hitches rather than a smooth fade —
  the fix needed to be "make each call cheap," not "call it less."
- **Drive colour through React state instead of direct material mutation.**
  Would reintroduce the exact per-render digest cost this ADR removes (every
  state update is a render, every render re-evaluates props) for up to
  ~1050 nodes per eased frame — the entire reason the original rAF-loop
  design (2026-09-01) avoided React state for this in the first place.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
