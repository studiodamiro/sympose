---
title: "ADR-091 — Nebula Dock Knobs Surfaced Inline in Settings + Dock Visibility Toggle"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
  - settings
---

# ADR-091 — Nebula Dock Knobs Surfaced Inline in Settings + Dock Visibility Toggle

- **Status:** Accepted — amends ADR-088/ADR-090 (Ambient Knowledge Nebula,
  Explore/Focus). Implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

> **Note on authorship:** this entry documents a batch of already-implemented,
> uncommitted work found in the working tree during a later tidy-up pass, not
> narrated live as it was built. The Decision/Consequences below are read off
> the diff and its own code comments (several of which are quoted directly);
> the Alternatives rejected section is this pass's best-effort reconstruction
> of the trade-off, not a transcript of the original discussion.

## Context

`NebulaAppearanceSection` (Settings → Knowledge Nebula) exposed the
Explore/Focus switch and the Focus-scrim/panel-opacity knobs, but the rest of
the graph's knobs — Toggles, Display, Forces — lived only in `NebulaControls`,
the floating dock that only renders on screen while already in Explore. There
was no way to tune node size, link thickness, or the force-layout sliders from
Settings; you had to already be in Explore, looking at the graph, to reach
them.

Once every dock knob became reachable a second way, the floating dock itself
turned into a standing obstruction — its `w-64` card sits over a corner of the
canvas for as long as Explore is active, whether or not you're using it, now
that Settings offers the same controls without it in the way.

## Decision

- **`SliderRow`** (`nebula-controls.tsx`) gains a `layout` prop —
  `"stacked"` (unchanged default: label/value on their own line, full-width
  track below, what the `w-64` floating dock needs) or `"inline"` (label,
  value and track folded onto one `ControlRow` line, matching every toggle
  and segmented control around it instead of standing out as the only
  two-line row in a list). Re-exported as `NebulaSliderRow` for reuse outside
  this file.
- **`NebulaControls`** takes the same `layout` prop and threads it to every
  `SliderRow` it renders.
- **`NebulaAppearanceSection`** drops its own local, duplicate `SliderRow`
  (the Focus blur/tint and Panel opacity rows now use the shared
  `NebulaSliderRow` with `layout="inline"`) and renders `<NebulaControls
  layout="inline">` directly beneath — stripped of its floating-card chrome
  (`w-full rounded-none border-0 bg-transparent p-0 shadow-none
  backdrop-blur-none`) so its Toggles/Display/Forces sections read as more
  sub-sections of the page's own Knowledge Nebula section rather than a
  second surface embedded inside it.
- **A new `dock: boolean` preference** (`sympose:nebula.dock` cookie, default
  `true`) gates whether the floating dock renders in Explore at all, exposed
  as a "Dock in Explore" On/Off row in Settings, with the hint: *"Every knob
  below is also the floating dock shown in Explore — turn it off there for an
  unobstructed view once you're tuning from here instead."*
- **`ambient-nebula.tsx`**: the data-source badge (`live vault` / `bundled
  sample` · node count) moved from an independent `absolute bottom-4 left-4`
  position to stacking above the dock in one `flex flex-col` cluster at
  `bottom-4 right-4`, so the two can never overlap regardless of the dock's
  height — and so the badge has a well-defined position once the dock beneath
  it can be toggled off.
- **Along the way:** the Knowledge Nebula's node-hover tooltip (`force-graph`'s
  bundled `float-tooltip` package, wrapping the HTML
  `knowledge-nebula-shared.ts`'s `createNodeTooltip()` supplies) was injecting
  its own always-dark default background with enough padding to show as a
  visible off-palette halo around the theme-correct inner div in light mode.
  Neutralized with a `.float-tooltip-kap { padding: 0 !important; background:
  transparent !important; }` override in `index.css` — the package exposes no
  option for it, so this was the only way to reach a third-party wrapper
  element that isn't part of this codebase.

## Consequences

- Every graph knob is now reachable from two places (Settings, always; the
  dock, while in Explore and turned on) that both write the same
  `NebulaPreferences` cookies — no divergent state between the two.
- The floating dock is opt-out, not mandatory chrome, on the strength of
  Settings now offering full parity.
- `NebulaSliderRow`'s two layouts mean any future slider added to the shared
  `NebulaControls` set automatically gets both a Settings-appropriate inline
  row and a dock-appropriate stacked one for free.

## Alternatives rejected

- **Keep the dock as the only place to tune Display/Forces, add just the
  Explore/Focus switch and scrim knobs to Settings (the pre-existing
  scope).** Simpler, but leaves the core "shape of the graph" knobs
  reachable only while already in the one mode most likely to have the
  panel you'd rather be looking at.
- **A single shared `SliderRow` used verbatim in both places, accepting the
  two-line stacked look in Settings too.** Fewer branches in the component,
  but stacked rows read as visually inconsistent against every toggle and
  segmented control around them once embedded in a page that otherwise
  never uses two-line rows.
- **Make the dock always-off by default now that Settings has parity, rather
  than an opt-out toggle defaulting on.** Riskier for anyone already relying
  on the dock's quick-access position while orbiting the graph; defaulting
  it on preserves the existing experience and only asks for a decision from
  someone who has an actual reason to hide it.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
