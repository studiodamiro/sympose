import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import { PANEL_CAP, type Breakpoint } from "@/lib/use-breakpoint"

/**
 * The three stage panels, in fixed left-to-right DOM order. "Open" here means
 * "occupies the stage" — for chat that is its body (transcript + composer); its
 * top-right action group is always present regardless.
 */
export type StagePanel = "content" | "editor" | "chat"

const PANEL_ORDER: StagePanel[] = ["content", "editor", "chat"]
const ORDER_COOKIE = "sympose:shell.order"

/** How long an evicted panel gets to slide out before the newcomer slides in. */
const SEQUENCE_MS = 320

/** Parse the persisted intent (oldest-first), dropping anything unrecognised. */
function readOrder(): StagePanel[] {
  const raw = getCookie(ORDER_COOKIE)
  if (raw == null) return ["chat"] // first run
  const seen = new Set<StagePanel>()
  return raw
    .split(",")
    .filter((p): p is StagePanel => PANEL_ORDER.includes(p as StagePanel))
    .filter((p) => (seen.has(p) ? false : (seen.add(p), true)))
}

/** The `cap` most-recently-opened panels — what actually shows at this width. */
function visibleSlice(order: StagePanel[], cap: number): StagePanel[] {
  return order.length > cap ? order.slice(order.length - cap) : order
}

export interface Panels {
  /** Is this panel on the stage right now? */
  isOpen: (p: StagePanel) => boolean
  /** Open it — if that hits the cap, the oldest showing panel slides out first. */
  open: (p: StagePanel) => void
  close: (p: StagePanel) => void
  toggle: (p: StagePanel) => void
  /** The panels actually on the stage right now, left-to-right (== DOM order). */
  visible: StagePanel[]
}

/**
 * Stage-panel visibility with an oldest-wins eviction cap. The full intent lives
 * in one cookie; the breakpoint's cap is a *view* over it, never a mutation — so
 * a desktop three-panel layout survives a tablet detour and returns intact.
 * Eviction is sequenced: the outgoing panel gets `SEQUENCE_MS` to leave before
 * the newcomer arrives, so the two don't animate over each other.
 */
export function usePanels(breakpoint: Breakpoint): Panels {
  const cap = PANEL_CAP[breakpoint]
  const [order, setOrder] = React.useState<StagePanel[]>(readOrder)
  const timer = React.useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  )

  React.useEffect(() => {
    setCookie(ORDER_COOKIE, order.join(","))
  }, [order])

  React.useEffect(() => () => clearTimeout(timer.current), [])

  const visible = React.useMemo(() => visibleSlice(order, cap), [order, cap])

  const appendCapped = React.useCallback(
    (o: StagePanel[], p: StagePanel) => {
      const next = [...o.filter((x) => x !== p), p]
      while (next.length > cap) next.shift()
      return next
    },
    [cap]
  )

  const open = React.useCallback(
    (p: StagePanel) => {
      const vis = visibleSlice(order, cap)
      if (vis.includes(p)) return
      clearTimeout(timer.current)
      if (vis.length >= cap) {
        // Evict the oldest showing panel now; let it leave, then bring `p` in.
        const evicted = vis[0]
        setOrder((o) => o.filter((x) => x !== evicted))
        timer.current = setTimeout(() => {
          setOrder((o) => appendCapped(o, p))
        }, SEQUENCE_MS)
      } else {
        setOrder((o) => appendCapped(o, p))
      }
    },
    [order, cap, appendCapped]
  )

  const close = React.useCallback((p: StagePanel) => {
    clearTimeout(timer.current)
    setOrder((o) => (o.includes(p) ? o.filter((x) => x !== p) : o))
  }, [])

  const toggle = React.useCallback(
    (p: StagePanel) => {
      if (visibleSlice(order, cap).includes(p)) close(p)
      else open(p)
    },
    [order, cap, open, close]
  )

  const isOpen = React.useCallback(
    (p: StagePanel) => visible.includes(p),
    [visible]
  )

  return { isOpen, open, close, toggle, visible }
}
