import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

const COOKIE = "sympose:vault.pinned"

function readPinned(): Set<string> {
  const raw = getCookie(COOKIE)
  return new Set(raw ? raw.split(",").filter(Boolean) : [])
}

/**
 * Pinned note paths — cookie-backed per the UI-preference convention, not a
 * vault write. Prep work ahead of the Pinned/Recent list (see the right-click
 * "Pin note" row): local-only for now, so pinning something costs nothing
 * more than a few bytes in a cookie — no round-trip, no vault frontmatter
 * write, no server involved. Promoting this to a durable, cross-device
 * pin (a frontmatter field on the note itself) is a later call once the
 * actual Pinned/Recent surface is built.
 */
export function usePinnedNotes(): {
  isPinned: (path: string) => boolean
  togglePin: (path: string) => void
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

  const isPinned = React.useCallback((path: string) => pinned.has(path), [pinned])

  return { isPinned, togglePin }
}
