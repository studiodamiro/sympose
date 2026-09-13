import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

const COOKIE = "sympose:vault.pinned"

function readPinned(): Set<string> {
  const raw = getCookie(COOKIE)
  return new Set(raw ? raw.split(",").filter(Boolean) : [])
}

/**
 * Pinned note paths — cookie-backed per the UI-preference convention, not a
 * vault write: local-only, so pinning something costs nothing more than a
 * few bytes in a cookie — no round-trip, no vault frontmatter write, no
 * server involved. Promoting this to a durable, cross-device pin (a
 * frontmatter field on the note itself) is a later call.
 */
export function usePinnedNotes(): {
  isPinned: (path: string) => boolean
  togglePin: (path: string) => void
  unpinMany: (paths: string[]) => void
  /** Every currently pinned path, insertion order — resolved by the caller
   *  against the full vault tree for the vault-wide "Pinned" group. */
  pinnedPaths: string[]
} {
  const [pinned, setPinned] = React.useState<Set<string>>(readPinned)

  const togglePin = React.useCallback((path: string) => {
    setPinned((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      setCookie(COOKIE, [...next].join(","))
      return next
    })
  }, [])

  // Batched for "Unpin all" on a Pinned group caption — one state update and
  // one cookie write instead of `paths.length` sequential `togglePin` calls.
  const unpinMany = React.useCallback((paths: string[]) => {
    setPinned((prev) => {
      const next = new Set(prev)
      for (const path of paths) next.delete(path)
      setCookie(COOKIE, [...next].join(","))
      return next
    })
  }, [])

  const isPinned = React.useCallback((path: string) => pinned.has(path), [pinned])
  const pinnedPaths = React.useMemo(() => [...pinned], [pinned])

  return { isPinned, togglePin, unpinMany, pinnedPaths }
}
