---
title: "ADR-089 — Drop the Frosted-Panel Blur Knob (amends ADR-088)"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
---

# ADR-089 — Drop the Frosted-Panel Blur Knob (amends ADR-088)

- **Status:** Accepted — amends ADR-088 (Ambient Knowledge Nebula in the App
  Shell, Phase A). Implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-088 gave the content and editor panels a tri-state frosted surface —
`off` / `tint` / `blur` — driven by two knobs, `panelBlur` and `panelOpacity`,
both exposed in Settings → Knowledge Nebula. Its own "Known limit" section
already flagged the tension: `backdrop-filter` on a frosted panel reads the
composited pixels *after* the full-viewport Focus scrim (`focusBlur` /
`focusTint`) has already been applied, so a meaningfully-tinted Focus state
leaves little for the panel's own blur to reveal — the two knobs weren't
independent in practice.

Using it live, the lead's call: opacity alone reads clearly and carries the
"nebula showing through" effect on its own; the added backdrop blur read as
visual noise layered on top rather than a distinct, legible state.

## Decision

Drop `panelBlur` entirely. `.sy-frosted-panel` keeps exactly the opacity path
— `data-nebula-frost` is now a bi-state (`off` / `tint`) instead of a
tri-state (`off` / `tint` / `blur`), gated by `panelOpacity` alone.

- `NebulaPreferences.panelBlur` and its cookie (`sympose:nebula.panel_blur`)
  removed from `use-nebula-preferences.ts`.
- The "Panel blur" slider removed from `NebulaAppearanceSection`; "Panel
  opacity" stays, hint text no longer mentions blur.
- `app-shell.tsx`'s `data-nebula-frost` derivation and the `--sy-panel-blur`
  custom property removed; `--sy-panel-opacity` is the only var the shell root
  still sets for this surface.
- `index.css`: the `[data-nebula-frost="blur"] .sy-frosted-panel` rule and its
  `backdrop-filter` deleted; the editor transparency rule
  (`.stylo` → transparent under frost) now keys off `[data-nebula-frost="tint"]`
  alone instead of `:is(tint, blur)`.

### A coverage gap under the same tint rule

Once panel frost was opacity-only, a second gap surfaced: dropping `.stylo`
(stylo's root, painting `background: var(--stylo-bg)`) to transparent under
tint left the editor's actual text area and its formatting toolbar still
opaque. `.cm-editor`'s background comes from CodeMirror's own base theme,
injected via `EditorView.theme()` rather than a class-module rule the tint
selector could reach, and the toolbar (`[role="toolbar"]`, stylo's own
accessibility contract — stabler to select on than its hashed CSS-module
class name) sets `background: var(--stylo-bg)` directly on itself rather than
inheriting `.stylo`'s. Neither picked up the transparency `.stylo` alone
carried. `[data-nebula-frost="tint"] [data-slot="markdown-panel"] .stylo` in
`index.css` is now three selectors — `.stylo`, `.cm-editor`, and
`[role="toolbar"]` — all dropped to transparent together;
`.cm-scroller`/`.cm-content` needed no override, carrying no background of
their own. The per-line code-fence tint (`.cm-inplace-mono`) is deliberately
untouched — it survives frost the same way inline `code` shading does in the
rendered preview, so code still reads as code.

## Consequences

- One fewer cookie, one fewer slider, one fewer CSS rule — net simplification,
  no behavior lost that wasn't already fighting itself per ADR-088's own
  caveat.
- The frosted-panel surface is now single-purpose: opacity only. Anyone
  wanting a blurred-glass panel look would need to reopen this decision, not
  just turn a knob back up.
- No migration needed — a stale `sympose:nebula.panel_blur` cookie left in a
  browser from before this change is simply never read again (the `SPEC`
  table no longer has an entry for it); harmless.

## Alternatives rejected

- **Keep `panelBlur` but clamp/derive it from `focusTint`** so the two knobs
  stop fighting (e.g. scale the panel blur down as Focus tint rises). Solves
  the independence problem ADR-088 flagged, but adds a cross-knob formula for
  an effect the lead had already decided reads as noise regardless — treating
  the symptom instead of removing the knob.
- **Leave the slider in Settings at `0` by default, just retire the reasoning
  in the docs.** Cheaper to write, but leaves a knob in the UI that does
  something (a `24px` range) with no legible reason to reach for it — against
  the zero-bloat standard for exposed controls.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
