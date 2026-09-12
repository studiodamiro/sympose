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

  return {
    displayKey: frozen ? frozen.key : key,
    displayPayload: frozen ? frozen.payload : payload,
    exitDirection: frozen?.direction ?? null,
    enterDirection: !frozen && entered?.key === key ? entered.direction : null,
    onExitComplete,
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
 * scrollable canvas — only the canvas should move. Each branch below is
 * spelled out as a complete literal class string (not built by interpolating
 * a scope prefix onto each utility) because Tailwind's build-time scanner
 * only generates CSS for class names it can find verbatim in the source; a
 * templated `` `[&_${scope}]:${utility}` `` never appears as one token and
 * would silently compile to no rule at all.
 */
export function slideExitClassName(
  direction: SlideDirection,
  scopeToCmScroller?: boolean
) {
  if (scopeToCmScroller) {
    return direction === "back"
      ? "[&_.cm-scroller]:pointer-events-none [&_.cm-scroller]:animate-out [&_.cm-scroller]:fade-out-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:fill-mode-forwards [&_.cm-scroller]:slide-out-to-right"
      : "[&_.cm-scroller]:pointer-events-none [&_.cm-scroller]:animate-out [&_.cm-scroller]:fade-out-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:fill-mode-forwards [&_.cm-scroller]:slide-out-to-left"
  }
  return cn(
    "pointer-events-none animate-out fade-out-0 duration-thumb fill-mode-forwards",
    direction === "back" ? "slide-out-to-right" : "slide-out-to-left"
  )
}

export function slideEnterClassName(
  direction: SlideDirection,
  scopeToCmScroller?: boolean
) {
  if (scopeToCmScroller) {
    return direction === "back"
      ? "[&_.cm-scroller]:animate-in [&_.cm-scroller]:fade-in-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:slide-in-from-left"
      : "[&_.cm-scroller]:animate-in [&_.cm-scroller]:fade-in-0 [&_.cm-scroller]:duration-thumb [&_.cm-scroller]:slide-in-from-right"
  }
  return cn(
    "animate-in fade-in-0 duration-thumb",
    direction === "back" ? "slide-in-from-left" : "slide-in-from-right"
  )
}
