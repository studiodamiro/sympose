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
  // The full persisted intent — reordered (most-recently-opened last) but
  // never trimmed. There are only ever 3 possible panels, so this can't grow
  // unbounded; capping to the breakpoint is `visibleSlice`'s job alone, so a
  // panel hidden by a narrower cap is still remembered here and reappears on
  // its own once a wider one has room for it again.
  const [order, setOrder] = React.useState<StagePanel[]>(readOrder)
  // Panels hidden pending their slide-out, ahead of the newcomer that's
  // waiting to take their place — a set, not a single flag, since two
  // evictions can be in flight at once (a second open()/close() arriving
  // before the first's SEQUENCE_MS is up).
  const [pendingEvicts, setPendingEvicts] = React.useState<Set<StagePanel>>(
    () => new Set()
  )
  // One pending-append timer per panel being opened (not one shared ref) so
  // a second open()/close() within SEQUENCE_MS of an unrelated eviction
  // can't cancel it out from under it.
  const timers = React.useRef<
    Partial<Record<StagePanel, ReturnType<typeof setTimeout>>>
  >({})

  React.useEffect(() => {
    setCookie(ORDER_COOKIE, order.join(","))
  }, [order])

  React.useEffect(
    () => () => {
      for (const t of Object.values(timers.current)) {
        if (t) clearTimeout(t)
      }
    },
    []
  )

  const settlePending = React.useCallback((p: StagePanel) => {
    const t = timers.current[p]
    if (t) {
      clearTimeout(t)
      delete timers.current[p]
    }
  }, [])

  const visible = React.useMemo(() => {
    const base = visibleSlice(order, cap)
    return pendingEvicts.size === 0
      ? base
      : base.filter((p) => !pendingEvicts.has(p))
  }, [order, cap, pendingEvicts])

  const open = React.useCallback(
    (p: StagePanel) => {
      if (visible.includes(p)) return
      settlePending(p)
      if (visible.length >= cap) {
        // Hide the oldest showing panel now so it can slide out; `p` lands
        // — reordered to the end, never trimmed — only once it's had
        // SEQUENCE_MS to leave, so the two don't animate over each other.
        const evicted = visible[0]
        setPendingEvicts((s) => new Set(s).add(evicted))
        timers.current[p] = setTimeout(() => {
          delete timers.current[p]
          setPendingEvicts((s) => {
            if (!s.has(evicted)) return s
            const next = new Set(s)
            next.delete(evicted)
            return next
          })
          setOrder((o) => [...o.filter((x) => x !== p), p])
        }, SEQUENCE_MS)
      } else {
        setOrder((o) => [...o.filter((x) => x !== p), p])
      }
    },
    [visible, cap, settlePending]
  )

  const close = React.useCallback(
    (p: StagePanel) => {
      settlePending(p)
      setPendingEvicts((s) => {
        if (!s.has(p)) return s
        const next = new Set(s)
        next.delete(p)
        return next
      })
      setOrder((o) => (o.includes(p) ? o.filter((x) => x !== p) : o))
    },
    [settlePending]
  )

  const toggle = React.useCallback(
    (p: StagePanel) => {
      if (visible.includes(p)) close(p)
      else open(p)
    },
    [visible, open, close]
  )

  const isOpen = React.useCallback(
    (p: StagePanel) => visible.includes(p),
    [visible]
  )

  return { isOpen, open, close, toggle, visible }
}
