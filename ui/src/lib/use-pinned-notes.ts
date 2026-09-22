import * as React from "react"

import { useVaultScopedState } from "@/lib/use-vault-scoped-state"

const COOKIE = "sympose:vault.pinned"

function readPinned(raw: string | null): Set<string> {
  return new Set(raw ? raw.split(",").filter(Boolean) : [])
}

function serializePinned(pinned: Set<string>): string {
  return [...pinned].join(",")
}

/**
 * Pinned note paths — cookie-backed per the UI-preference convention, not a
 * vault write: local-only, so pinning something costs nothing more than a
 * few bytes in a cookie — no round-trip, no vault frontmatter write, no
 * server involved. Promoting this to a durable, cross-device pin (a
 * frontmatter field on the note itself) is a later call.
 *
 * Vault scoping and reseed-on-switch are `useVaultScopedState`'s job — see
 * its doc comment for why a pin isn't seeded synchronously from a cookie at
 * mount.
 */
export function usePinnedNotes(vaultPath: string | null): {
  isPinned: (path: string) => boolean
  togglePin: (path: string) => void
  unpinMany: (paths: string[]) => void
  /** Every currently pinned path, insertion order — resolved by the caller
   *  against the full vault tree for the vault-wide "Pinned" group. */
  pinnedPaths: string[]
} {
  const [pinned, setPinned] = useVaultScopedState(
    COOKIE,
    vaultPath,
    readPinned,
    serializePinned
  )

  const togglePin = React.useCallback(
    (path: string) => {
      setPinned((prev) => {
        const next = new Set(prev)
        if (next.has(path)) next.delete(path)
        else next.add(path)
        return next
      })
    },
    [setPinned]
  )

  // Batched for "Unpin all" on a Pinned group caption — one state update
  // instead of `paths.length` sequential `togglePin` calls.
  const unpinMany = React.useCallback(
    (paths: string[]) => {
      setPinned((prev) => {
        const next = new Set(prev)
        for (const path of paths) next.delete(path)
        return next
      })
    },
    [setPinned]
  )

  const isPinned = React.useCallback((path: string) => pinned.has(path), [pinned])
  const pinnedPaths = React.useMemo(() => [...pinned], [pinned])

  return { isPinned, togglePin, unpinMany, pinnedPaths }
}
