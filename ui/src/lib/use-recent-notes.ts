import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import { useVaultScopedState } from "@/lib/use-vault-scoped-state"

const HISTORY_COOKIE = "sympose:vault.recents"
const SHOWN_COOKIE = "sympose:vault.recents_shown"
const ENABLED_COOKIE = "sympose:vault.recents_enabled"

// History keeps more than is ever displayed, so raising the "shown" knob
// later doesn't need to have retroactively kept more than was visible at the
// time.
const MAX_STORED = 20
const DEFAULT_SHOWN = 5

function readHistory(raw: string | null): string[] {
  return raw ? raw.split(",").filter(Boolean) : []
}

function serializeHistory(history: string[]): string {
  return history.join(",")
}

function readShownCount(): number {
  const n = Number(getCookie(SHOWN_COOKIE))
  return Number.isFinite(n) && n > 0 ? n : DEFAULT_SHOWN
}

function readEnabled(): boolean {
  return getCookie(ENABLED_COOKIE) !== "0"
}

/**
 * Recently opened notes — "jump back to your working note", rendered as its
 * own group under Pinned in the vault panel. Same local-only convention as
 * `usePinnedNotes()`: a visit costs a few bytes in a cookie, no vault write,
 * no round-trip.
 *
 * History (up to `MAX_STORED` paths, most-recent-first, deduped) is tracked
 * separately from `shownCount` — a Settings knob capping how many actually
 * render — so raising the knob later isn't limited by how many were ever
 * displayed before.
 *
 * History is vault-scoped and reseeds on a vault switch via
 * `useVaultScopedState` — see its doc comment. `shownCount` / `enabled`
 * stay global, on their own plain cookie-backed state: they're layout
 * preferences, not vault content.
 */
export function useRecentNotes(vaultPath: string | null): {
  /** The most recent `shownCount` paths, most-recent-first — empty whenever
   *  `enabled` is off, regardless of how much history is actually stored. */
  recentPaths: string[]
  shownCount: number
  setShownCount: (n: number) => void
  /** Whether the "Recent" group renders at all (Settings toggle). History
   *  keeps recording either way, so switching back on immediately has
   *  something to show instead of starting over. */
  enabled: boolean
  setEnabled: (on: boolean) => void
  /** Record a note as just opened, moving it to the front. */
  recordVisit: (path: string) => void
  /** Drop one path out of the history — the "Recent" group's own per-row
   *  "Remove from recents" menu item. */
  removeFromRecents: (path: string) => void
  /** Empty the whole history — the "Recent" group caption's "Clear recents". */
  clearRecents: () => void
} {
  const [history, setHistory] = useVaultScopedState(
    HISTORY_COOKIE,
    vaultPath,
    readHistory,
    serializeHistory
  )
  const [shownCount, setShownCountState] = React.useState<number>(readShownCount)
  const [enabled, setEnabledState] = React.useState<boolean>(readEnabled)

  const recordVisit = React.useCallback(
    (path: string) => {
      setHistory((prev) => {
        if (prev[0] === path) return prev
        return [path, ...prev.filter((p) => p !== path)].slice(0, MAX_STORED)
      })
    },
    [setHistory]
  )

  const removeFromRecents = React.useCallback(
    (path: string) => {
      setHistory((prev) => prev.filter((p) => p !== path))
    },
    [setHistory]
  )

  const clearRecents = React.useCallback(() => {
    setHistory([])
  }, [setHistory])

  const setShownCount = React.useCallback((n: number) => {
    setCookie(SHOWN_COOKIE, String(n))
    setShownCountState(n)
  }, [])

  const setEnabled = React.useCallback((on: boolean) => {
    setCookie(ENABLED_COOKIE, on ? "1" : "0")
    setEnabledState(on)
  }, [])

  const recentPaths = React.useMemo(
    () => (enabled ? history.slice(0, shownCount) : []),
    [history, shownCount, enabled]
  )

  return {
    recentPaths,
    shownCount,
    setShownCount,
    enabled,
    setEnabled,
    recordVisit,
    removeFromRecents,
    clearRecents,
  }
}
