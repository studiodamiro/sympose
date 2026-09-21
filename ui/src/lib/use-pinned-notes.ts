import * as React from "react"

import { getCookie, setCookie, vaultScopedKey } from "@/lib/cookies"

const COOKIE = "sympose:vault.pinned"

function readPinned(key: string): Set<string> {
  const raw = getCookie(key)
  return new Set(raw ? raw.split(",").filter(Boolean) : [])
}

/**
 * Pinned note paths — cookie-backed per the UI-preference convention, not a
 * vault write: local-only, so pinning something costs nothing more than a
 * few bytes in a cookie — no round-trip, no vault frontmatter write, no
 * server involved. Promoting this to a durable, cross-device pin (a
 * frontmatter field on the note itself) is a later call.
 *
 * Scoped per `vaultPath` (see `vaultScopedKey`) — a pin is a reference into
 * one vault's content, meaningless in another, so each vault keeps its own
 * set.
 *
 * `pinned` isn't seeded synchronously from a cookie at mount — which vault
 * is active usually isn't known yet then (`vaultPath` starts `null` until
 * the caller's own vault fetch answers), so `key` would still be the bare,
 * unscoped key. The reseed effect below resolves the real value once the
 * key is actually known.
 */
export function usePinnedNotes(vaultPath: string | null): {
  isPinned: (path: string) => boolean
  togglePin: (path: string) => void
  unpinMany: (paths: string[]) => void
  /** Every currently pinned path, insertion order — resolved by the caller
   *  against the full vault tree for the vault-wide "Pinned" group. */
  pinnedPaths: string[]
} {
  const key = vaultScopedKey(COOKIE, vaultPath)
  const [pinned, setPinned] = React.useState<Set<string>>(new Set())

  // Resolve/reseed `pinned` whenever the scope key changes — the first
  // resolution from the bare key (before `vaultPath` is known) to a real
  // vault's key, and every later A-to-B switch, are handled the same way:
  // read whatever *this* key already has (or none), rather than continuing
  // to show the previous vault's.
  const prevKey = React.useRef<string | null>(null)
  React.useEffect(() => {
    if (key === prevKey.current) return
    prevKey.current = key
    setPinned(readPinned(key))
  }, [key])

  const togglePin = React.useCallback(
    (path: string) => {
      setPinned((prev) => {
        const next = new Set(prev)
        if (next.has(path)) next.delete(path)
        else next.add(path)
        setCookie(key, [...next].join(","))
        return next
      })
    },
    [key]
  )

  // Batched for "Unpin all" on a Pinned group caption — one state update and
  // one cookie write instead of `paths.length` sequential `togglePin` calls.
  const unpinMany = React.useCallback(
    (paths: string[]) => {
      setPinned((prev) => {
        const next = new Set(prev)
        for (const path of paths) next.delete(path)
        setCookie(key, [...next].join(","))
        return next
      })
    },
    [key]
  )

  const isPinned = React.useCallback((path: string) => pinned.has(path), [pinned])
  const pinnedPaths = React.useMemo(() => [...pinned], [pinned])

  return { isPinned, togglePin, unpinMany, pinnedPaths }
}
