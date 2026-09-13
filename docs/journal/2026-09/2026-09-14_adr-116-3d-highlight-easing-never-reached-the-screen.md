---
title: "ADR-116 — 3D Highlight/Dim Easing Never Reached the Screen (amends ADR-112, ADR-115)"
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

# ADR-116 — 3D Highlight/Dim Easing Never Reached the Screen (amends ADR-112, ADR-115)

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

After ADR-115 removed 3D's duplicate background-click dispatch, damiro still
saw the same symptom: click a node and "every node lights up and zooms in";
click empty space and "only a few light up." Direct console instrumentation
of `selectedNodeId` and `highlightedNodeIds` (added temporarily to
`ambient-nebula.tsx`) proved the *state* was correct on every single click in
his real session — a hub tag narrowed to its true 208 members, a sparse note
to its true 3-4 links, a background click always reset to all 1089. No
inversion, no staleness, no wrong node, across a long real trace.

To isolate rendering from the camera, `handleNodeClick`'s `flyCameraTo` call
was temporarily disabled (camera never moves) so damiro could judge the
dim/highlight in place. The result was unchanged: "nothings correct when I
clicked any nodes" — with the camera now provably not a factor, this located
the bug definitively in the 3D renderer's paint step, not the state layer or
the zoom.

Reading `knowledge-nebula-3d.tsx`'s highlight machinery again with that
constraint in hand: a `requestAnimationFrame` loop eases each node's
`__highlightT` (0 = dimmed, 1 = highlighted) toward its target every frame via
`stepHighlightT`, mutating the property directly on the node's data object.
`nodeColor` reads `__highlightT` to compute the rendered colour. The loop's own
comment claimed "three.js re-evaluates `nodeColor` every frame regardless" —
that's what would make mutating the property enough on its own. It's false.
Reading `three-forcegraph.mjs` directly: node materials are only rebuilt from
inside `_rerender()`, gated behind `state._flushObjects || hasAnyPropChanged([...,
'nodeColor', ...])` — i.e. only when a *prop* changes (a new `nodeColor`
closure reference from a React re-render) or `.refresh()` is called explicitly.
Mutating a plain property on a plain object, off in an independent rAF loop
that never touches React state, does neither. The eased value was being
computed continuously and never once drawn — the colour actually on screen
was whatever `nodeColor` happened to evaluate to the last time some *unrelated*
prop change forced `KnowledgeNebula3D` to re-render, decoupled entirely from
the click that supposedly drove it. That explains both the inconsistency
(the odd click *did* look right, by the accident of an unrelated re-render
landing at a moment `__highlightT` had drifted somewhere plausible) and the
flat "nothing's correct" once the zoom's own re-renders were no longer around
to occasionally paper over it.

**2D never had this problem** because its canvas renderer redraws
unconditionally every frame by construction — there's no material-diffing
layer to route around, so mutating a value ahead of the next paint just works.

## Decision

`stepHighlightT` already returned whether a node was still short of its
target — declared for exactly this purpose in its own doc comment ("so the
caller's animation loop knows whether to keep ticking this node") but never
actually consumed anywhere. Wired it up: the rAF loop now tracks whether any
node eased this frame and calls `fg.refresh()` — `three-forcegraph`'s own hook
for "something changed outside your props, please rebuild the affected
materials" — only while that's true, not unconditionally every frame forever
once everything's settled.

## Consequences

- Verified visually (Playwright, camera-fly still disabled from the isolation
  step): before the fix, clicking a node left the entire graph fully coloured
  with no visible change; after, the same click correctly dims the whole
  graph to grey except the clicked node and its direct links.
- This was the actual bug behind every symptom reported across ADR-112,
  ADR-114, and ADR-115's testing — the state layer, the click dispatch, and
  the mount-crash fix were all independently real and correct, but none of
  them could have produced a correct-looking result on screen while this sat
  underneath.
- damiro confirmed on his real vault (904 notes/783 links, `app.py
  --dashboard`) that node clicks now narrow the highlight correctly (a person
  note to its 36 links, a tag to its 3, a date to its 3-4), matching the
  `highlightedNodeIds` sizes exactly. The camera-fly-on-node-click code in
  `handleNodeClick`, disabled for this isolation test, is re-enabled.
- The temporary `[NEBULA-DEBUG]` console instrumentation (`ambient-nebula.tsx`)
  and a `[PERF-DEBUG]` timing probe added while investigating a separate
  "animation feels off" report (which turned out to be unrelated — see below)
  have both been removed.
- Investigated a follow-up report that "the animation is off": timed
  `fg.refresh()` directly (0.0–0.1ms per call) — it isn't the cost. The
  broader "entire app feels jerky" turned out to be about `shouldRotate =
  autoRotate || dimmed` (pre-existing, from the original 3D renderer commit,
  not introduced by ADR-112/114/115/116): the ambient background camera
  auto-rotates continuously whenever the nebula is merely dimmed (i.e. in
  ordinary Focus mode), independent of the user's own "Auto rotate" setting.
  That's a real, likely-continuous cost while 3D is selected, but it's an
  original ambient-visual design choice, not a regression from this ADR chain
  — left as a separate, still-open discussion with damiro rather than changed
  unilaterally here.
- Process note: this fix's source changes ended up sitting in a `git stash`
  (damiro's own unrelated WIP was stashed on top of a tree that already had
  these edits) and were reintroduced into `main` via a `git stash pop` bundled
  into an unrelated, already-pushed commit
  (`098e509 fix(ui): reclaim reserved gutter for note/folder row menu
  trigger`) — meaning this ADR's fix, plus the leftover debug logging above,
  shipped to `origin/main` under a commit message that doesn't mention it.
  The cleanup in this same change (debug removal, camera-fly re-enable) is a
  separate, correctly-labelled follow-up commit rather than a history rewrite
  of the already-pushed commit.
- `.venv/bin/pytest` (414 passed), `npm run typecheck`, `npm run build` all
  clean; `sympose/webui/` rebuilt.

## Alternatives rejected

- **Make `nodeColor` itself trigger correctly some other way (e.g. always
  return a fresh closure identity via a ref-read wrapper).** `nodeColor` is
  already a fresh closure every render — the problem was never closure
  identity, it was that *nothing forced a render* in response to the rAF
  loop's mutations. A refresh call is the library's own documented mechanism
  for exactly this; reaching for closure tricks would be solving a problem
  that doesn't exist while leaving the real one (no signal to redraw) unfixed.
- **Drive `__highlightT` through React state instead of a rAF loop mutating
  plain objects.** Would make every eased frame a React re-render for up to
  ~1050 nodes, defeating the entire reason this was built as an out-of-band
  rAF loop in the first place (documented in the original 2026-09-01 session
  as deliberately cheap). `fg.refresh()` gets the same result — the library
  redraws using current data — without paying a React render per frame.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
