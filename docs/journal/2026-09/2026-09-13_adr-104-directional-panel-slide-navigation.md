---
title: "ADR-104 — Directional Slide for Content/Editor Panel Navigation"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-104 — Directional Slide for Content/Editor Panel Navigation

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

Switching the content panel's active folder/section, or the editor's open
note, was an instant, un-animated DOM swap — the panel's own open/close
transition (`content-panel.tsx`, `markdown-panel.tsx`: fade + `marginInlineStart`
tween, driven by their `open` prop) only ever covered the panel *revealing*
or *hiding*, never one piece of content replacing another while the panel
stays open. damiro flagged this directly as feeling cheap and asked for a
sideways slide instead, tied to the content panel's existing back/forward
toolbar (ADR-095's visit-history stack over `active`) — left for forward
navigation, right for back, matching ordinary browser conviction.

## Decision

**A new generic hook, `useSlideSwap<T>` (`ui/src/lib/use-slide-swap.ts`)**,
gives a single content slot a sequential (never-overlapping) directional
slide: a `key` change freezes the outgoing payload and plays its slide-out;
the caller's live payload for the new key is only shown — with its own
slide-in — once that exit reports done via `onAnimationEnd`, the same
CSS-driven completion contract `useAnimatedNodeList` (ADR-103) already
established, rather than a guessed `setTimeout`. The very first payload a
caller ever passes shows with no enter animation, so app boot never plays a
spurious slide.

Wired at two call sites:

- **`app-shell.tsx`** — the content panel's folder/section body. A new
  `contentDirection` state (`"back" | "forward"`) is set alongside whatever
  triggers the `active` change: `"back"` from the back-arrow button,
  `"forward"` from the forward-arrow button *and* every other pick (a menu
  item, a vault-tree folder) — any destination that isn't a history
  traversal reads as "forward," same as a browser pushing a new page.
- **`markdown-panel.tsx`** — the editor's open note. There is no
  back/forward concept for individual notes (only the content panel's
  folder/section history is tracked), so every note switch — a wikilink, a
  vault-tree pick, a newly created note — is fixed at `"forward"`.

Both read `duration-thumb` (300ms, ADR-102) for the exit and the enter half
alike, kept in the same tier `<ScrollThumb>` and vault-tree rows already use
rather than inventing a new number, and re-tuned once during the session:
damiro tried the faster `duration-snappy` (150ms) tier and asked to revert
to `duration-thumb` — 300ms per leg reads smoother for a full-panel swap
than the row-scale motion `snappy`/`thumb` were originally tuned for.

**Stylo's toolbar stays fixed — only the CodeMirror canvas slides.** Stylo
(`@damiro/stylo`) mounts its own formatting toolbar and the CodeMirror
editing surface as one component tree it fully owns (its stylesheet shows a
`_root_` flex column containing a `_toolbar_` row and an `_inplace_` canvas
pane as siblings) — there is no prop-level seam to pull them apart, and
stylo is a fixed external dependency this project does not patch. Wrapping
the whole mount in the slide would have dragged the toolbar along with the
document, which damiro also flagged directly ("we shouldn't animate the
toolbars"). The fix scopes the slide/fade CSS to a descendant selector
targeting `.cm-scroller` — CodeMirror's own stable, public scroll-viewport
class, already relied on elsewhere in this file for `<ScrollThumb>` — so
only the document surface moves and the toolbar sibling never gets a
transform at all. `MarkdownPanel` freezes a `hasToolbar` flag alongside each
note's payload (via `useSlideSwap`'s generic `T`) so an *exiting* "ready"
note still knows to scope its own slide-out correctly even after
`note.status` has already moved on to the next note.

## Two real bugs found while building this, fixed in the same change

**1. A one-frame flicker of the outgoing content right as its exit
finished.** tw-animate-css's `--animate-out` defaults to
`animation-fill-mode: none`; the instant an exit keyframe's declared
duration elapses, the browser reverts the element to its un-animated (fully
visible, untranslated) base style for one paint — before the `onAnimationEnd`
listener's React state update actually swaps the DOM node out. Confirmed via
a `requestAnimationFrame` sampler polling `getComputedStyle` across a real
transition: without the fix, opacity/transform briefly snapped back to
`1`/`none` at the exact exit-end frame. Fixed by adding `fill-mode-forwards`
to the exit classes, pinning the end-of-exit state until the swap actually
happens.

**2. A scoped-animation class helper that silently compiled to zero CSS.**
The first version of the `.cm-scroller`-scoping helper built each class name
via a template literal (`` `[&_${scope}]:${utility}` ``). Tailwind's
build-time scanner only generates CSS for class names it can find *verbatim*
as a contiguous string somewhere in a source file — it does not evaluate
JavaScript, so a name assembled at runtime from separate fragments never
appears as one token anywhere in the file and produces no rule at all. The
classes were present in the rendered DOM and did precisely nothing. Fixed by
spelling each direction/scope combination out as a complete literal string
(verified by grepping the built `sympose/webui/assets/index-*.css` for the
expected `.cm-scroller`-scoped rules before and after — absent, then
present).

## Consequences

- Content-panel folder/section switches now slide left (forward) or right
  (back), matching the back/forward toolbar's own arrows; editor note
  switches always slide in from the right.
- Exit and enter never overlap — the outgoing content fully leaves before
  the incoming content starts arriving, verified by sampling computed
  `transform`/`opacity` across a real transition (continuous descent to
  `opacity: 0` off-screen, then an immediate, distinct jump to the enter
  phase from the opposite side).
- Stylo's own toolbar is provably static throughout a note-switch slide
  (isolated-harness check: toolbar `transform` stayed `none` while
  `.cm-scroller` animated) — the "don't animate chrome" rule this ADR
  establishes generalizes to any future panel animation, not just this one.
- `useSlideSwap<T>` is generic over its payload, not content-panel- or
  editor-specific — reusable for any other single-slot content area that
  later wants the same back/forward-aware, exit-then-enter treatment.
- The `.cm-scroller` descendant-selector coupling is to CodeMirror's own
  public class name, not stylo's internal (hashed) CSS-module classes — a
  stylo upgrade that changes its *own* toolbar/canvas markup wouldn't break
  this, only a CodeMirror major version that renamed `.cm-scroller` itself
  would (unlikely; already an existing dependency of `<ScrollThumb>`).

## Alternatives rejected

- **`framer-motion` / `AnimatePresence`.** Rejected per the zero-bloat/
  no-new-dependency stance (ADR-103's own precedent) — a `key`-driven
  freeze-then-swap hook plus tw-animate-css's existing `animate-in`/
  `animate-out` utilities covers sequential exit/enter without a new runtime
  dependency.
- **A `setTimeout` matched to the CSS duration**, instead of
  `onAnimationEnd`. Rejected for the same reason as ADR-103: a JS-side
  timer duplicating a number that already lives in CSS can silently drift
  from it; `onAnimationEnd` cannot.
- **Reaching into stylo's own internal CSS-module class names** (e.g.
  `_toolbar_1lohh`, visible only in its shipped stylesheet) to exclude the
  toolbar from the slide. Rejected: those are stylo's private,
  hash-suffixed implementation detail, not a contract this project can rely
  on across a stylo version bump — `.cm-scroller` is CodeMirror's own
  public, stable class and already an existing integration point.
- **Skipping the animation for the editor's "ready" (Stylo-mounted) state
  entirely**, animating only the empty/loading/error placeholders. Rejected:
  opening an actual note is the dominant navigation case the feature was
  asked for; punting on it would have shipped the animation for the case
  that matters least.
- **A faster shared tier (`duration-snappy`, 150ms) for both legs.** Tried
  first, then explicitly reverted by damiro back to `duration-thumb`
  (300ms) — noted here rather than silently overwritten, since it was a
  deliberate two-way call, not a default either tier was obviously "right."

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `cd ui && npx eslint <changed files>` — no new findings beyond
  pre-existing, unrelated `react-hooks/refs` warnings already present on
  `main`.
- A scratch Playwright session against the running `:5173` dev server
  (`chromium.launch()`, `getComputedStyle` polling via
  `requestAnimationFrame`) confirmed: (a) forward navigation slides content
  left-then-in-from-right and back navigation the mirror; (b) exit
  completes fully (`opacity: 0`, fully off-screen) before any enter-phase
  class appears — no overlap; (c) after the `fill-mode-forwards` fix, no
  flicker back to the un-animated state at the exit/enter boundary. A
  second, isolated static-HTML harness (loading the app's own compiled
  `index.css` against a hand-built toolbar+`.cm-scroller` DOM shape)
  confirmed the toolbar's `transform` stays `none` throughout while
  `.cm-scroller` slides. Screenshots and scripts were scratch-only, not
  checked into the repo.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
