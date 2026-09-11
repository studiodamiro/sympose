---
title: "ADR-094 — Settings Panel Density Cleanup"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - settings
---

# ADR-094 — Settings Panel Density Cleanup

- **Status:** Accepted — implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

Settings has grown enough top-level `ControlSection`s — Markdown editor,
Notifications, Knowledge Nebula (the last nesting `NebulaControls`' own
Toggles/Display/Forces sections) — that scanning past all of them to reach one
row is now real friction. Two smaller papercuts sat alongside that:

- **Uneven row height.** `ControlRow` centers a label against whatever control
  it's handed. A segmented-control/toggle row lands around 28–30px tall
  (`size="sm"` button + padding + border); a slider row's native
  `<input type="range">` track is only `h-1.5` (6px), so that row's height
  collapsed to the label's own line-height (~20px) instead. Toggle rows and
  slider rows down the same list read as uneven vertical rhythm.
- **Stale header copy.** The "← back to demos" link was a holdover from
  before Settings was a first-class destination reachable from the main menu,
  and the paragraph under the heading ("Every menu row toggles this panel;
  click the active row again to slide it away...") describes generic
  panel-toggle behavior that isn't specific to Settings and no longer earns
  its space now that the feature is established.

## Decision

- **`ControlRow`** (`control-section.tsx`) — the shared row primitive behind
  every toggle, segmented control, and slider row — gets `min-h-7`. This
  raises a slider row's overall height to match its toggle siblings without
  touching the slider's own thin `h-1.5` track, so the fix corrects rhythm
  without changing the control's visual weight.
- **Settings header** (`app-shell.tsx`): the intro paragraph and the "back to
  demos" link are gone. The heading row now holds just the title and one new
  control.
- **Collapse-all.** `control-section.tsx` adds a `ControlSectionsProvider` +
  `useCollapseAll` context and a ready-made `CollapseAllButton`
  (`ListCollapseIcon`), wired into the Settings header. Each `ControlSection`
  keeps its own open/closed `useState`; the provider only broadcasts a pulse
  (an incrementing signal), and every section beneath it — however deeply
  nested, including `NebulaControls`' Toggles/Display/Forces inside Knowledge
  Nebula — forces itself shut once on that pulse, then stays independently
  toggleable again afterward. Outside a provider (the components gallery),
  `useCollapseAll` is a no-op and `ControlSection` behaves exactly as the
  plain uncontrolled `defaultOpen` it always was.

## Consequences

- The `min-h-7` fix lives on the one shared primitive, so it corrects the
  row-height inconsistency everywhere `ControlRow` is used — Settings, the
  floating nebula dock, and the components gallery — not just the spot it was
  first noticed.
- The collapse-all pulse is scoped by React context to whatever subtree a
  `ControlSectionsProvider` wraps. The Settings page's sections respond to its
  own button; the ambient nebula's separate floating dock (also built from
  `NebulaControls`, mounted outside the Settings subtree, shown in Explore)
  is untouched by it — correct, since it's a different surface with its own
  lifecycle.
- Caught a React-StrictMode-only bug while building this: the first cut used
  a mutable "have I mounted" ref to skip the pulse effect's first run, which
  flips on React's dev-only double effect invocation and collapsed every
  section on first paint. Fixed by comparing against the last *handled*
  signal value instead of a boolean flag — idempotent no matter how many
  times the mount effect actually runs, in Strict Mode or out of it.

## Alternatives rejected

- **Grow `SliderRow`'s own track height instead of `ControlRow`'s
  min-height.** Fixes the one component that surfaced the problem, but
  leaves any future control with a naturally short row unaddressed and would
  need repeating per control shape — `ControlRow` is the row primitive
  precisely so this kind of fix lands once.
- **A real expand/collapse toggle** (the button relabels to "Expand all" once
  everything is shut, tracking every section's boolean centrally). More
  discoverable in theory, but requires the provider to fully control every
  section's state rather than fire a pulse, for what's a single frequent
  action — scan the headings, dive into one section. Revisit if usage shows
  people want "restore what I had open" rather than "shut everything."
- **A Settings search box instead of collapse-all.** Solves "find the one row
  I want" more directly, but is materially bigger (matching, highlighting)
  for a page that currently has three top-level sections; revisit if the
  section count keeps growing.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
