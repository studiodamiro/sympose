import * as React from "react"

import { cn } from "@/lib/utils"

export type SlideDirection = "back" | "forward"

interface Frozen<T> {
  key: string
  payload: T
  direction: SlideDirection
}

interface EnteredMark {
  key: string
  direction: SlideDirection
}

/**
 * Sequential, never-overlapping directional slide for a single content slot
 * (the content/editor panel's folder or note body) — a `key` change freezes
 * the outgoing payload long enough to play its slide-out; the caller's live
 * payload for the new key is only shown, with its own slide-in, once that
 * finishes (`onExitComplete`, fired by the frozen element's own
 * `onAnimationEnd` — the same CSS-driven contract `useAnimatedNodeList`
 * (ADR-103) uses rather than a guessed timeout, so this can't drift out of
 * sync with whatever duration the CSS actually uses).
 *
 * `payload` is opaque (typically the content node, sometimes bundled with a
 * bit of metadata a caller needs frozen alongside it — see `MarkdownPanel`'s
 * `hasToolbar`) — this hook only ever tracks and hands it back, never reads
 * into it.
 *
 * The very first payload a caller ever passes is shown as-is, with no enter
 * animation — only a genuine key change (real navigation) animates.
 */
export function useSlideSwap<T>(
  key: string,
  payload: T,
  direction: SlideDirection
) {
  const lastKeyRef = React.useRef(key)
  const lastPayloadRef = React.useRef(payload)
  const [frozen, setFrozen] = React.useState<Frozen<T> | null>(null)
  const [entered, setEntered] = React.useState<EnteredMark | null>(null)

  React.useEffect(() => {
    if (key === lastKeyRef.current) {
      lastPayloadRef.current = payload
      return
    }
    setFrozen({
      key: lastKeyRef.current,
      payload: lastPayloadRef.current,
      direction,
    })
    lastKeyRef.current = key
    lastPayloadRef.current = payload
  }, [key, payload, direction])

  const onExitComplete = React.useCallback(() => {
    setFrozen((current) => {
      if (current) setEntered({ key: lastKeyRef.current, direction: current.direction })
      return null
    })
  }, [])

  // Without this, `entered` (and the `slideEnterClassName` scoped classes it
  // drives) would sit on the ancestor forever after a switch — including the
  // `--tw-enter-translate-*` custom properties those classes set on the very
  // same `.cm-scroller`/`.sy-note-preview`/`.sy-note-chrome` descendants a
  // *later*, unrelated animation on the same elements (`MarkdownPanel`'s
  // read/edit toggle) also targets. A still-matching stale rule and the new
  // one both set `animation`/the custom properties on the same element, and
  // which one's translate value wins comes down to CSS source order, not
  // which is semantically "active" — the toggle's meant-to-be-pure-fade
  // content silently inherited a leftover slide from the last note switch.
  // Clearing `entered` once its own enter animation genuinely finishes (via
  // `onAnimationEnd`, not a guessed timeout) drops that stale class the
  // moment it's no longer needed.
  const onEnterComplete = React.useCallback(() => {
    setEntered(null)
  }, [])

  return {
    displayKey: frozen ? frozen.key : key,
    displayPayload: frozen ? frozen.payload : payload,
    exitDirection: frozen?.direction ?? null,
    enterDirection: !frozen && entered?.key === key ? entered.direction : null,
    onExitComplete,
    onEnterComplete,
  }
}

/**
 * Both read `duration-thumb` (ADR-102) — same "enters and leaves at the same
 * speed" rule the vault-tree row's own exit/entrance already follows.
 * `fill-mode-forwards` is load-bearing on the exit half: tw-animate-css's
 * `animate-out` defaults to `animation-fill-mode: none`, so the instant the
 * exit keyframe finishes, the element snaps back to its un-animated (fully
 * visible, untranslated) style for one paint — the outgoing content flickers
 * back before `onAnimationEnd` swaps it out — unless the end state is pinned.
 *
 * `scopeToCmScroller` targets CodeMirror's own `.cm-scroller` descendant
 * instead of the element carrying these classes, for a caller (`MarkdownPanel`)
 * whose content bundles a fixed chrome row (the Stylo toolbar) alongside the
 * scrollable canvas — only the canvas should move. The same scope also drives
 * `.sy-note-footer` (the wikilink-pills bar under the canvas): unlike the
 * toolbar it's per-note content, not fixed chrome, so it rides along with the
 * canvas's slide rather than sitting frozen mid-transition while the note
 * underneath it moves. `.sy-note-preview` is the same idea for stylo's
 * `mode="preview"` — it has no `.cm-scroller` at all (no CodeMirror instance),
 * so without a scope selector of its own a note switch while read-only left
 * the whole panel sitting frozen (the wrapping element itself was never given
 * `animate-out`/`animate-in`, only its `.cm-scroller` descendant was, and
 * preview has none) instead of sliding.
 *
 * `.sy-note-chrome` is the toolbar row itself (`MarkdownPanel`'s breadcrumb
 * in read mode, stylo's own formatting bar in edit mode) — a genuinely
 * different animation from the content above, not just the same slide
 * applied to a second element: it always moves vertically, never left/right
 * (a plain `slide-out-to-top`/`slide-in-from-top` pair covers both nav
 * directions, no `direction` branch needed), and it runs on `duration-snappy`
 * (ADR-102) — faster than content's `duration-thumb` — deliberately, so the
 * two are never racing to finish at the same instant. `onExitComplete` is
 * wired to fire from content's own `animationend` only (`MarkdownPanel`
 * filters by `event.target`), so a note switch's chrome settling early can
 * never fire the commit ahead of content and truncate it mid-slide. Chrome
 * carries `fade-out-0`/`fade-in-0` too (not just the slide nudge) precisely
 * because it settles first: without a fade, `fill-mode-forwards` pins the
 * old breadcrumb fully opaque — just offset by a hair — for the whole gap
 * until content catches up, so the swap to the new path text (an instant DOM
 * replacement, not itself animated) reads as an abrupt cut. Fading to
 * transparent by the time it's sitting in that gap, and back in once the new
 * one mounts, hides the actual replacement inside invisible time instead of
 * flashing it.
 * Each branch below is spelled out as a complete literal class string (not
 * built by interpolating a scope prefix onto each utility) because
 * Tailwind's build-time scanner only generates CSS for class names it can
 * find verbatim in the source; a templated `` `[&_${scope}]:${utility}` ``
 * never appears as one token and would silently compile to no rule at all.
 *
 * `animateChrome` (default on) lets a `scopeToCmScroller` caller drop the
 * `.sy-note-chrome` rule entirely — for `MarkdownPanel`'s edit-mode toolbar,
 * whose buttons are identical across every note. Unlike the read-mode
 * breadcrumb (whose text is the thing changing), nothing about that row
 * actually differs after the switch, so sliding/fading it was motion with
 * no real change behind it. `false` here doesn't just skip the animation
 * classes, it omits the selector altogether — the row is never given
 * `animate-out`/`animate-in` at all and simply sits still.
 */
export function slideExitClassName(
  direction: SlideDirection,
  scopeToCmScroller?: boolean,
  animateChrome = true
) {
  if (scopeToCmScroller) {
    return cn(
      direction === "back"
        ? cn(
            "[&_.cm-scroller]:pointer-events-none [&_.cm-scroller]:animate-out [&_.cm-scroller]:fade-out-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:fill-mode-forwards [&_.cm-scroller]:slide-out-to-right",
            "[&_.sy-note-footer]:pointer-events-none [&_.sy-note-footer]:animate-out [&_.sy-note-footer]:fade-out-0 [&_.sy-note-footer]:duration-thumb [&_.sy-note-footer]:fill-mode-forwards [&_.sy-note-footer]:slide-out-to-right",
            "[&_.sy-note-preview]:pointer-events-none [&_.sy-note-preview]:animate-out [&_.sy-note-preview]:fade-out-0 [&_.sy-note-preview]:duration-thumb [&_.sy-note-preview]:fill-mode-forwards [&_.sy-note-preview]:slide-out-to-right"
          )
        : cn(
            "[&_.cm-scroller]:pointer-events-none [&_.cm-scroller]:animate-out [&_.cm-scroller]:fade-out-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:fill-mode-forwards [&_.cm-scroller]:slide-out-to-left",
            "[&_.sy-note-footer]:pointer-events-none [&_.sy-note-footer]:animate-out [&_.sy-note-footer]:fade-out-0 [&_.sy-note-footer]:duration-thumb [&_.sy-note-footer]:fill-mode-forwards [&_.sy-note-footer]:slide-out-to-left",
            "[&_.sy-note-preview]:pointer-events-none [&_.sy-note-preview]:animate-out [&_.sy-note-preview]:fade-out-0 [&_.sy-note-preview]:duration-thumb [&_.sy-note-preview]:fill-mode-forwards [&_.sy-note-preview]:slide-out-to-left"
          ),
      animateChrome &&
        "[&_.sy-note-chrome]:pointer-events-none [&_.sy-note-chrome]:animate-out [&_.sy-note-chrome]:fade-out-0 [&_.sy-note-chrome]:duration-snappy [&_.sy-note-chrome]:fill-mode-forwards [&_.sy-note-chrome]:slide-out-to-top-1"
    )
  }
  return cn(
    "pointer-events-none animate-out fade-out-0 duration-thumb fill-mode-forwards",
    direction === "back" ? "slide-out-to-right" : "slide-out-to-left"
  )
}

export function slideEnterClassName(
  direction: SlideDirection,
  scopeToCmScroller?: boolean,
  animateChrome = true
) {
  if (scopeToCmScroller) {
    return cn(
      direction === "back"
        ? cn(
            "[&_.cm-scroller]:animate-in [&_.cm-scroller]:fade-in-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:slide-in-from-left",
            "[&_.sy-note-footer]:animate-in [&_.sy-note-footer]:fade-in-0 [&_.sy-note-footer]:duration-thumb [&_.sy-note-footer]:slide-in-from-left",
            "[&_.sy-note-preview]:animate-in [&_.sy-note-preview]:fade-in-0 [&_.sy-note-preview]:duration-thumb [&_.sy-note-preview]:slide-in-from-left"
          )
        : cn(
            "[&_.cm-scroller]:animate-in [&_.cm-scroller]:fade-in-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:slide-in-from-right",
            "[&_.sy-note-footer]:animate-in [&_.sy-note-footer]:fade-in-0 [&_.sy-note-footer]:duration-thumb [&_.sy-note-footer]:slide-in-from-right",
            "[&_.sy-note-preview]:animate-in [&_.sy-note-preview]:fade-in-0 [&_.sy-note-preview]:duration-thumb [&_.sy-note-preview]:slide-in-from-right"
          ),
      animateChrome &&
        "[&_.sy-note-chrome]:animate-in [&_.sy-note-chrome]:fade-in-0 [&_.sy-note-chrome]:duration-snappy [&_.sy-note-chrome]:slide-in-from-top-1"
    )
  }
  return cn(
    "animate-in fade-in-0 duration-thumb",
    direction === "back" ? "slide-in-from-left" : "slide-in-from-right"
  )
}
