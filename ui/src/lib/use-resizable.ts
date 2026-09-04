import * as React from "react"

import { getCookieNumber, setCookie } from "@/lib/cookies"

type Bound = number | (() => number)

const val = (b: Bound) => (typeof b === "function" ? b() : b)
const clamp = (n: number, lo: number, hi: number) =>
  Math.min(Math.max(n, lo), hi)

export interface UseResizableOptions {
  /** Lower bound in px. A function is re-evaluated on window resize. */
  min: Bound
  /** Upper bound in px. A function is re-evaluated on window resize. */
  max: Bound
  /** Initial size in px when there is no stored value. */
  defaultSize: Bound
  /**
   * Handle edge. `"end"` (default) — handle on the right, drag right = larger.
   * `"start"` — handle on the left, drag left = larger.
   */
  edge?: "start" | "end"
  /** Cookie key for persisting the committed size as a user preference. */
  storageKey?: string
  /**
   * Final transform applied on drag-release / keyboard commit — e.g. snapping
   * below a threshold. Returns the size to settle on.
   */
  onCommit?: (size: number) => number
}

export interface ResizeHandleProps {
  role: "separator"
  "aria-orientation": "vertical"
  "aria-valuemin": number
  "aria-valuemax": number
  "aria-valuenow": number
  tabIndex: 0
  onPointerDown: (e: React.PointerEvent<HTMLElement>) => void
  onPointerMove: (e: React.PointerEvent<HTMLElement>) => void
  onPointerUp: (e: React.PointerEvent<HTMLElement>) => void
  onPointerCancel: (e: React.PointerEvent<HTMLElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => void
}

/**
 * Drag/keyboard resize for one axis. Owns clamping, cookie persistence, and
 * re-clamping when function bounds change on window resize. Spread `handleProps`
 * onto the drag handle element.
 */
export function useResizable({
  min,
  max,
  defaultSize,
  edge = "end",
  storageKey,
  onCommit,
}: UseResizableOptions) {
  const [size, setSizeState] = React.useState(() => {
    const stored = storageKey ? getCookieNumber(storageKey) : null
    const initial = stored ?? val(defaultSize)
    return clamp(initial, val(min), val(max))
  })
  const [dragging, setDragging] = React.useState(false)
  const origin = React.useRef<{ x: number; size: number } | null>(null)

  const setSize = React.useCallback(
    (next: number) => setSizeState(clamp(next, val(min), val(max))),
    [min, max]
  )

  const commit = React.useCallback(
    (next: number) => {
      let settled = clamp(next, val(min), val(max))
      if (onCommit) settled = clamp(onCommit(settled), val(min), val(max))
      setSizeState(settled)
      if (storageKey) setCookie(storageKey, String(Math.round(settled)))
      return settled
    },
    [min, max, onCommit, storageKey]
  )

  // Re-clamp on mount (bounds that read layout aren't known during the initial
  // `useState`) and whenever the viewport changes. `min`/`max` functions must be
  // stable (wrap in `useCallback`) or this runs every render.
  React.useEffect(() => {
    const reclamp = () => setSizeState((s) => clamp(s, val(min), val(max)))
    reclamp()
    window.addEventListener("resize", reclamp)
    return () => window.removeEventListener("resize", reclamp)
  }, [min, max])

  const dir = edge === "end" ? 1 : -1

  const handleProps: ResizeHandleProps = {
    role: "separator",
    "aria-orientation": "vertical",
    "aria-valuemin": Math.round(val(min)),
    "aria-valuemax": Math.round(val(max)),
    "aria-valuenow": Math.round(size),
    tabIndex: 0,
    onPointerDown: (e) => {
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      origin.current = { x: e.clientX, size }
      setDragging(true)
    },
    onPointerMove: (e) => {
      if (!origin.current) return
      setSize(origin.current.size + dir * (e.clientX - origin.current.x))
    },
    onPointerUp: (e) => {
      if (!origin.current) return
      origin.current = null
      setDragging(false)
      try {
        e.currentTarget.releasePointerCapture(e.pointerId)
      } catch {
        /* already released */
      }
      commit(size)
    },
    onPointerCancel: () => {
      origin.current = null
      setDragging(false)
      commit(size)
    },
    onKeyDown: (e) => {
      const step = e.shiftKey ? 48 : 16
      let next: number | null = null
      if (e.key === "ArrowRight") next = size + step
      else if (e.key === "ArrowLeft") next = size - step
      else if (e.key === "Home") next = val(min)
      else if (e.key === "End") next = val(max)
      if (next == null) return
      e.preventDefault()
      commit(next)
    },
  }

  return { size, setSize, commit, dragging, handleProps }
}
