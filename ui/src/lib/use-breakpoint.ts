import * as React from "react"

/**
 * App-shell size classes, keyed off the shell's own rendered width (kept
 * deliberately simple — see the tablet-responsiveness spec). iPad Mini sits on
 * the 768 / 1280 boundaries, so it reads as `tablet` in both orientations.
 *
 * - `phone`   — `< 768`   (layout is a later pass)
 * - `tablet`  — `768–1279` (≤ 2 stage panels, editor toolbar wraps)
 * - `desktop` — `≥ 1280`  (all 3 stage panels inline)
 */
export type Breakpoint = "phone" | "tablet" | "desktop"

/** Max stage panels ({content, editor, chat}) visible at once, per breakpoint. */
export const PANEL_CAP: Record<Breakpoint, number> = {
  phone: 1,
  tablet: 2,
  desktop: 3,
}

function classify(width: number): Breakpoint {
  if (width >= 1280) return "desktop"
  if (width >= 768) return "tablet"
  return "phone"
}

/**
 * Breakpoint from a live measurement of `ref`'s element — the shell root, which
 * fills the viewport. Measuring the actual box (via `ResizeObserver`) rather
 * than `window.innerWidth` / `matchMedia` avoids the stale first reads those can
 * give (dev overlays, embedded webviews, headless). Falls back to `desktop`
 * until the element mounts.
 */
export function useBreakpoint(
  ref: React.RefObject<HTMLElement | null>
): Breakpoint {
  const [bp, setBp] = React.useState<Breakpoint>("desktop")

  React.useEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => setBp(classify(el.getBoundingClientRect().width))
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])

  return bp
}
