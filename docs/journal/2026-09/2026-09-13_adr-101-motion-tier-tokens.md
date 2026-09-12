---
title: "ADR-101 — Motion Tier Tokens (`snappy` / `mode`)"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-101 — Motion Tier Tokens (`snappy` / `mode`)

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

`docs/wiki/reference/ui-design-reference.md` already states a motion rule of
thumb — "calm motion: 120–180ms snappy transitions in the UI, 300–400ms for
mode-level cross-fades" — and several components' own comments confirm it was
being followed by hand: `content-panel.tsx` says its reveal transition uses
`ease-in-out`, "not `ease-out` — matches `<MarkdownPanel>` and the chat slot's
own reveal transitions," and `app-shell.tsx`'s chat slot and `<MarkdownPanel>`
both independently landed on `duration-300 ease-in-out`. But nothing enforced
the pairing: every call site inlined its own `duration-*`/`ease-*` Tailwind
utility classes, so three components staying in sync depended on whoever
touched one of them remembering to check the other two, with no compiler or
lint signal if they drifted.

This surfaced concretely while adding entrance animations for the wikilink
footer pills and new vault-tree rows: they landed on an ad hoc `duration-200`,
a fourth value with no relation to either the 120–180ms micro-interaction
bracket or the 300–400ms panel bracket the rest of the app was already using.

## Decision

Two named motion tiers, defined once in `ui/src/index.css` and referenced by
class name everywhere instead of inlined literals:

- **`snappy`** — micro-interactions: hover fades, a pill or row entering,
  small collapse/expand toggles. `150ms`, `ease-out`.
- **`mode`** — panel-/layout-level reveals: panel open/close, the chat slot,
  phone-mode crossfades, the frontmatter card's grid-row reveal. `350ms`,
  `ease-in-out`.

Each tier is a duration class plus an easing class, used together
(`duration-snappy ease-snappy` / `duration-mode ease-mode`):

```css
/* Easing: --ease-* is a real Tailwind v4 theme namespace, so this alone
   generates the `ease-snappy` / `ease-mode` utility classes. */
@theme inline {
  --ease-snappy: cubic-bezier(0, 0, 0.2, 1);   /* ease-out */
  --ease-mode: cubic-bezier(0.4, 0, 0.2, 1);   /* ease-in-out */
}

/* Duration: `--duration-*` is *not* a themeable namespace in Tailwind v4
   (unlike `--color-*` / `--radius-*`) — verified empirically, the class
   silently failed to generate when defined that way. `@utility` is the
   correct v4 primitive for a custom utility outside the built-in namespaces. */
@utility duration-snappy { transition-duration: 150ms; }
@utility duration-mode { transition-duration: 350ms; }
```

Migrated to the tokens: `<MarkdownPanel>`'s wrapper reveal, phone crossfade,
and frontmatter-card grid-row transitions; `<ContentPanel>`'s reveal
transition; `app-shell.tsx`'s chat action group and chat slot transitions
(all four `duration-300 ease-in-out` → `duration-mode ease-mode`); the new
wikilink-pill and vault-tree-row entrance animations (`duration-200` → the
now-correct `duration-snappy`); and two exact-value matches,
`control-section.tsx`'s collapsible content and `app-shell.tsx`'s inline
rename-input reveal (`duration-150 ease-out` → `duration-snappy ease-snappy`,
same computed values, just referencing the shared token).

## Consequences

- The three previously hand-synced "mode"-tier components can no longer drift
  silently — they all reference the same class.
- The pill/row entrance animations now sit in the documented 120–180ms
  bracket (150ms) instead of an arbitrary 200ms.
- New components have an explicit choice between the two tiers instead of
  picking a fresh number.

## Alternatives rejected

- **`--duration-*` as an `@theme` namespace**, mirroring `--color-*`. Tried
  first since it's the pattern every other token in `index.css` follows —
  confirmed via a build check that Tailwind v4 does not treat `--duration-*`
  as a recognized theme namespace, so no `duration-snappy`/`duration-mode`
  utility was generated (silently, no build error) until switched to
  `@utility`.
- **A JS/TS constants module** (`motion.ts`) exporting duration/easing
  strings for template-literal class names. Rejected: Tailwind's static
  class-name scanning can't see through a runtime-interpolated class list, so
  this would need a `safelist` entry per token — more moving parts than a
  plain CSS utility for the same two values.
- **Migrating every `duration-*`/`ease-*` occurrence in the codebase**
  (`main-menu.tsx`'s 200ms sidebar collapse; `ambient-nebula.tsx`,
  `knowledge-nebula-2d/3d.tsx`, `capacity-meter.tsx`'s 300ms canvas/meter
  effects; `scroll-thumb.tsx`'s ADR-100-tuned 300ms `ease-out` hover fade).
  Rejected for this change: the panel-level and newly-added call sites were
  either already documented as intentionally coupled or had no rationale at
  all (worth converging), but the rest are either a different visual value
  that would need an explicit product decision to change (main-menu's 200ms),
  a distinct semantic category (ambient/canvas effects, not a UI reveal), or
  an already-recorded, deliberate ADR-100 taste call — forcing any of them
  onto `snappy`/`mode` now would silently change behavior no one asked to
  change.

## Deferred (additive)

- `main-menu.tsx`'s sidebar-collapse transition (200ms `ease-out`) is a
  candidate for `snappy` if a future change wants it to match exactly, but
  that's a real (if small) timing change, not a token substitution — left for
  whoever touches that component next to decide deliberately.
- The canvas/ambient-effect durations (nebula, capacity meter) are a
  different semantic category from UI reveals and weren't evaluated for a
  third tier here.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
