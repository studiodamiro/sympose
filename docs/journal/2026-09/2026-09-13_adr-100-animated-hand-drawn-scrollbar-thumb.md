---
title: "ADR-100 — Animated Hand-Drawn Scrollbar Thumb"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-100 — Animated Hand-Drawn Scrollbar Thumb

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

The editor's scrollbar (stylo's `.cm-scroller`) never faded to invisible at
rest the way the rest of the app's scroll surfaces do. Root cause: stylo ships
its own `.cm-scroller` scrollbar styling (`dist/styles.css`) that colors the
thumb unconditionally, with no `:hover` gate, at the same CSS specificity as
the app's own auto-hide rule — so it always won regardless of stylesheet
order.

Two follow-on attempts to animate the *native* scrollbar turned out to be dead
ends, each verified rather than assumed:

- **A `transition` on `::-webkit-scrollbar-thumb` / `scrollbar-color`.**
  Chromium does not animate color changes on native scrollbar pseudo-elements
  — they're painted outside the normal compositor/transition pipeline. The
  CSS is accepted but has no visible effect.
- **`scroll-behavior: smooth` on `.cm-scroller`**, to at least ease
  CodeMirror's own jump-to-position scrolling (search results, click-to-line,
  cursor-follow while typing). Checked against `@codemirror/view`'s actual
  source: every internal scroll-to-position call funnels through
  `scrollRectIntoView` (`index.js`), which does a raw `cur.scrollTop +=
  moveY` — a plain property write. `scroll-behavior` only affects scrolls
  performed via `scrollTo()`/`scrollBy()`/`scrollIntoView()` without an
  explicit `behavior`; a raw `scrollTop` assignment is always instant and
  entirely unaffected by that CSS property. CodeMirror never distinguishes
  "jump" scrolls from "typing-follow" scrolls at the API level either, so
  even patching around this would have no clean way to animate one without
  the other.

Getting a real, animated fade meant not relying on the native scrollbar at
all.

## Decision

**`<ScrollThumb>`** (`ui/src/components/sympose/scroll-thumb.tsx`) — a small,
hand-drawn scrollbar standing in for the native one wherever it's mounted:

- A `rail` (full-height click target, invisible) holds a `thumb` (the visible,
  draggable piece). Being a real DOM node, the thumb's hover fade is a
  genuine, animatable CSS `opacity` transition (300ms `ease-out`) — not a
  native color change.
- Geometry (`top`/`height`) is computed from the actual scroller's
  `getBoundingClientRect()` relative to a `position: relative` container ref,
  recalculated on `scroll`, a `ResizeObserver` on the container, and a
  `window resize` listener.
- `getScroller(container)` is a caller-supplied resolver rather than an
  assumed stable ref, since stylo remounts `.cm-scroller` on note/mode
  switches; a `MutationObserver` on the container re-binds whenever the
  resolved element changes.
- Dragging the thumb scrolls proportionally; clicking the bare rail
  above/below the thumb pages the scroller by one `clientHeight` (instant,
  by design — see Alternatives Rejected) — restoring the native
  track-click behavior lost by hiding the real scrollbar.
- The real native scrollbar is hidden outright (`scrollbar-width: none`,
  `::-webkit-scrollbar { display: none }`) wherever `<ScrollThumb>` is
  mounted, in `index.css`.

Two mount points:

- **The editor** (`markdown-panel.tsx`): `getScroller` resolves
  `.cm-scroller` via `querySelector` inside the wrapper already holding
  `<Stylo>`.
- **`<ContentPanel>`** (`content-panel.tsx`) — the shared shell for the vault
  view, Settings, and the Agent page. Its scroll surface was previously the
  same element that carried the frosted background and rounded corners, which
  can't also host a thumb that stays pinned while the content scrolls beneath
  it (an absolutely-positioned child of a scrolling element scrolls away with
  it; only a non-scrolling ancestor works). Introduced a
  `position: relative; overflow-hidden` wrapper to hold the background/corner
  classes and anchor the thumb, with the actual `overflow-y-auto` surface now
  an `inset-0` layer inside it. One change here lands on every `<ContentPanel>`
  consumer at once.

## Consequences

- The fade is now real and consistent between the editor and every
  `<ContentPanel>` surface, instead of the editor alone having a
  (non-animating) always-visible thumb.
- One shared component instead of duplicating the drag/measure/page-click
  logic per mount point.
- Each mount costs one `MutationObserver` + one `ResizeObserver` + one
  `scroll` listener + one `resize` listener, bound once per mount (a stable,
  module-level `getScroller` reference, not an inline closure) — bounded, O(1)
  per callback, the same order of cost as the existing `useFillWidth` hook.
- `content-panel.tsx`'s scroll surface gained one extra wrapper `div`; the
  rounded-corner/background classes moved from the (formerly) scrolling
  element to that wrapper. Low visual risk since the classes moved verbatim,
  but it's a widely shared component, so worth calling out for anyone
  touching its corner-rounding logic next.
- Wheel/trackpad scrolling and CodeMirror's own internal scroll-to-position
  calls (typing-follow, search jumps) remain exactly as fast/instant as
  native scrolling always was — deliberately out of scope, not a gap (see
  Alternatives Rejected).

## Alternatives rejected

- **CSS `transition` on the native scrollbar thumb/color.** Doesn't animate
  in Chromium regardless of syntax — verified empirically, not assumed.
- **CSS `scroll-behavior: smooth` on `.cm-scroller`.** Verified against
  `@codemirror/view` source: every CodeMirror-internal scroll (typing-follow,
  search jumps, click-to-position) sets `scrollTop` as a raw property write,
  which `scroll-behavior` cannot affect. A no-op, not a partial win.
- **Patching CodeMirror's `scrollTop` setter** to intercept every write and
  ease it, using a size heuristic (animate large jumps, snap small
  typing-follow deltas) to approximate "jump" vs. "typing." Rejected: sits on
  top of stylo/CodeMirror internals we've agreed to treat as a fixed external
  dependency, fragile across version bumps, and risks visual jitter since
  CodeMirror synchronously re-reads `scrollTop` right after setting it to
  recompute its own virtualized viewport.
- **App-wide custom wheel/trackpad momentum scrolling** (re-implementing
  smooth-scroll physics, the way marketing-site libraries like Lenis do).
  Rejected on inspection, not just as bloat-in-principle: it requires
  non-passive wheel listeners, which block the compositor from scrolling
  until our JS runs on every tick (a real, documented perf cost, not
  hypothetical); it double-decays trackpad input that already carries native
  OS momentum, producing the "mushy" feel common to bad smooth-scroll
  implementations; and it would run permanently against the editor's own
  scroll-driven virtualization. Fails the project's zero-bloat bar for a
  purely cosmetic gain — native scrolling stays as-is.
- **Reusing the already-installed Base UI `<ScrollArea>` primitive**
  (`components/ui/scroll-area.tsx`) instead of a hand-rolled thumb.
  Considered for `<ContentPanel>` specifically, since it's fully React-owned
  and would have been a smaller diff there — but CodeMirror requires
  exclusive ownership of its own scrolling element for virtualization, so
  Base UI's `ScrollArea.Viewport` can never wrap `.cm-scroller`. Using it in
  one spot and a hand-rolled thumb in the other would mean two different
  scrollbar implementations for what's meant to read as one consistent
  scrollbar; building `<ScrollThumb>` once and reusing it everywhere kept
  that consistency instead.
- **Easing the rail's click-to-page jump** via `scrollTo({behavior:
  "smooth"})` — unlike the CodeMirror-internal cases above, this one *was*
  safely animatable, since it's our own call, not CodeMirror's. Implemented,
  then reverted at damiro's request: he preferred the page-jump stay an
  instant snap and wanted only the hover fade eased. Recorded here as a
  taste call, not a technical dead end.

## Deferred (additive)

- `chat-panel.tsx` and `main-menu.tsx` each have their own separate native
  `overflow-y-auto` surface, untouched by this ADR. Extending `<ScrollThumb>`
  to them is a straightforward repeat of the `<ContentPanel>` pattern if
  wanted later; not gating this change.

## B.4 index updates

`docs/PROJECT_JOURNAL.md`, `docs/wiki/index.md`, and
`docs/wiki/architecture/dashboard-and-vault-explorer.md` updated in the same
change.
