---
title: "ADR-093 — Stage Action Group Order Swap & Explore Slide-Out"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
---

# ADR-093 — Stage Action Group Order Swap & Explore Slide-Out

- **Status:** Accepted — implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

The stage's top-right corner carries two action-group chips, rendered as
siblings above the content/editor/chat panels: `<NebulaModeToggle>` (the
Focus/Explore affordance, ADR-090) and `<ChatActionGroup>` (new conversation /
bookmark). They shipped in the order Focus-toggle, then chat/bookmark.

Two papercuts with that arrangement:

- Reading order put the Focus/Explore switch — a mode toggle for the whole
  shell — ahead of chat/bookmark, the pair that actually acts on the panel
  directly beneath it.
- ADR-090 already force-closes chat behind the scenes the moment Explore is
  entered, but the chat/bookmark chip itself just sat there unchanged — a
  clickable-looking affordance for a panel that Explore has already put out of
  reach.

## Decision

- Swap render order in `app-shell.tsx`'s stage action-group row:
  `<ChatActionGroup>` first, `<NebulaModeToggle>` second. The Focus/Explore
  switch is the fixed anchor in the corner in both modes (it's the way back to
  Focus); chat/bookmark sits nearer the panel it controls.
- `<ChatActionGroup>` now takes a `transition-[opacity,translate] duration-300
  ease-in-out` className, gated on `explore`: `translate-x-4 opacity-0
  pointer-events-none` in Explore, `translate-x-0 opacity-100` in Focus. It
  slides out to the right and fades as Explore is entered, and slides back in
  on the way to Focus — the same opacity+translate idiom the chat panel's own
  stage slot (`chatSlotRef`) already uses for its open/close transition, kept
  consistent rather than introducing a second "leaving" pattern.

## Consequences

- No new state or cookie — purely a `className` and a JSX reorder in
  `app-shell.tsx`.
- Chat/bookmark now visually agrees with ADR-090's behavior: it disappears
  when it isn't actionable instead of sitting inert on top of the vault graph.

## Alternatives rejected

- **Leave both chips static, only restyle chat/bookmark's disabled state in
  Explore.** Simpler, but a dimmed-but-present icon still reads as clickable
  at a glance; ADR-090 already fully closes the door, so the affordance should
  leave, not just grey out.
- **Fade opacity only, no translate.** Marginally less code, but breaks with
  the existing precedent (the chat panel's own slot) for how a stage element
  leaves on a mode change — two different "leaving" idioms on the same stage
  would read as inconsistent rather than as one coherent motion language.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
