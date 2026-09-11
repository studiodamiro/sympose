---
title: "ADR-090 — Explore Auto-Collapses the Stage Panels (amends ADR-088)"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
---

# ADR-090 — Explore Auto-Collapses the Stage Panels (amends ADR-088)

- **Status:** Accepted — amends ADR-088 (Ambient Knowledge Nebula in the App
  Shell, Phase A), closing out its deferred Phase B item. Implemented
  2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-088 shipped Explore/Focus with interactivity coming from the stage giving
up pointer events — but an **open** panel always stayed on top, visible and
clickable, in either mode. Its own Consequences section named the resulting
gap directly: *"Phase A still doesn't auto-collapse open panels to the edges
on entering Explore as the design reference specifies... so seeing the graph
while a panel is open still means closing it yourself."* Its Alternatives
rejected section deferred the fix to a "Phase B" rather than bloating the
shell edit that introduced the layer.

In practice this meant Explore mode was unusable exactly when you'd reach for
it: switch to Explore with the chat (or content, or editor) panel open, and it
just sits there covering the graph, unclickable-through, because each of the
three stage panels reclaims `pointer-events-auto` for itself regardless of
mode (by design — an open panel must stay interactive). The lead hit this
directly and asked for the panels to animate out on entering Explore so the
canvas is actually reachable.

## Decision

`AppShell` now reacts to `nebulaPrefs.interaction` changes:

- **Entering Explore** — snapshot `panels.visible` (whatever of content /
  editor / chat is currently on stage, in their existing left-to-right order)
  into a ref, then `panels.close()` each one. They animate out through the
  same slide/fade transitions `usePanels` already drives for any close.
- **Returning to Focus** — reopen the stashed panels, oldest-first, via
  `panels.open()`. `usePanels`' own breakpoint-cap and eviction logic (tablet
  caps two, phone caps one) applies exactly as it would to any other open
  call, so the restore can't put more panels on stage than the current
  breakpoint allows.
- The snapshot lives in a `React.useRef`, not state — it doesn't need to
  trigger a render, and stashing it in the same `usePanels` cookie-backed
  `order` would have persisted the pre-Explore layout as if the user had
  actually closed those panels, corrupting the "what was open" signal the
  breakpoint-return logic elsewhere in the shell also depends on.
- The effect keys off `nebulaPrefs.interaction` alone (not the `panels` object,
  whose identity changes on every panel-order write) via a ref holding the
  latest `panels` handle, so it fires exactly once per actual mode flip.

### The graph still wasn't clickable — a second, older bug under the first

After the above shipped, Explore auto-collapsed the panels but the nebula
still didn't respond to clicks, drags, or the dock's own sliders. Verifying
with Playwright's `elementFromPoint` at the canvas center and at a slider
showed both resolving to the same element: the "menu + stage row" wrapper —
`<div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden">`
one level above the stage div ADR-088 documented as `pointer-events-none`.
That inner stage div *was* correctly `pointer-events-none` with its children
reclaiming `auto`, exactly as ADR-088 describes — but the row wrapping *it and
`<MainMenu>` together* was never given the same treatment. With no
`pointer-events: none` on that row, its own box — covering the full menu +
stage width, painted above the fixed nebula layer — was a valid hit target in
its own right, so once the stage's excluded subtree had nothing reclaiming a
given point, hit-testing fell back to this outer row instead of continuing
through to the nebula beneath it. This predates today's panel-collapse work —
ADR-088 shipped it — it just had no way to surface until panels could
actually get out of the way for something to click on.

Fixed the same way as the stage div: the row gets `pointer-events-none`, and
`<MainMenu>` (its other child, which must stay clickable in both modes)
reclaims `pointer-events-auto` explicitly, the same pattern the stage panels
already use one level down.

Reverified with the same Playwright rig: `elementFromPoint` at the canvas
center now resolves to the `<canvas>` itself and at a dock slider to the
`<input>`; dragging the Repel-force slider moves its value, and a mouse-drag
on the canvas visibly pans the graph.

### A faster way in

Settings → Knowledge Nebula's `Explore | Focus` switch still exists, but
burying the *only* entry point to a "go interact with the graph now" mode
three levels into Settings fought the feature's own purpose. Added
`<NebulaModeToggle>` — a single icon button (orbit glyph), same visual idiom
as the existing `<ChatActionGroup>` chip (`bg-secondary` shell around a
`size-7` button, `aria-pressed` state) — parked beside it at the stage's
top-right corner, desktop/tablet only (mirroring `ChatActionGroup`'s own
`!isPhone` gate; phone's `TopBar` is already at capacity and Explore's
click-and-drag interaction model doesn't translate to a touch shell the same
way regardless — not addressed here).

## Consequences

- Explore now does what ADR-088's own Consequences section said it should:
  entering it clears the stage, the full graph becomes click-and-drag
  interactive immediately, no manual panel-closing first.
- Verified live (Playwright against a scratch dev-server port): toggling
  Explore slides the open chat panel fully off-stage (`x: -224` outside the
  viewport) while `[data-slot="ambient-nebula"]` flips to
  `data-interaction="explore"` and the control dock / folder legend render;
  toggling back to Focus restores the same panel. Separately, the
  pointer-events fix above was verified the same way — see that section.
- One more piece of shell state (the stash ref) — scoped to `AppShell`, not
  persisted, not a new cookie; a page reload while in Explore simply has
  nothing stashed to restore, which is correct (there's nothing to restore
  across a reload the user didn't initiate).
- The Settings switch and the new corner toggle both write the same
  `nebulaPrefs.interaction` cookie — no divergent state between the two entry
  points.

## Alternatives rejected

- **Wrap the interaction-setting call sites instead of an effect on the pref.**
  Would need every call site (the Settings row, the new toggle, any later one)
  to remember to stash/restore correctly; an effect on the pref value itself
  makes the collapse behavior a property of *entering Explore*, not of *how*
  you entered it — one place to get right instead of N.
- **Persist the stash in the existing panel-order cookie.** Reuses
  `usePanels`' own storage instead of a new ref, but a Focus↔Explore round-trip
  would then read from the cookie as "the user closed these panels," which is
  wrong — they didn't, Explore did, and other logic in the shell (e.g. the
  breakpoint-return cap) trusts that cookie as user intent.
- **Also give the phone shell a corner toggle.** Consistent with desktop, but
  the phone `TopBar` is already carrying the brand mark, vault button,
  Settings, account, and chat actions — another icon there needs its own
  design pass, not a drive-by addition, and Explore's orbit-and-pan model is
  a genuinely different interaction on a touch surface than on a pointer one.
  Left for whoever designs phone Explore properly.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
