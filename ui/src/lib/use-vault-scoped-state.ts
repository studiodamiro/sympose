import * as React from "react"

import { getCookie, setCookie, vaultScopedKey } from "@/lib/cookies"

/**
 * A `useState` value scoped to the active vault and persisted in a cookie —
 * shared plumbing behind `usePinnedNotes`, `useRecentNotes`, and
 * app-shell's `selectedNote`. A pinned set, a recent-notes list, an open
 * note path — each is a reference into one vault's content, meaningless in
 * another, so each vault gets its own value under its own scoped cookie key
 * (`vaultScopedKey`).
 *
 * Deliberately *not* seeded synchronously from a cookie at mount — which
 * vault is active usually isn't known yet then (`vaultPath` starts `null`
 * until the caller's own vault fetch answers), so the scoped key would
 * still be the bare, unscoped one. The reseed effect below resolves the
 * real value once the key is actually known, uniformly for that first
 * resolution and every later vault switch — no special-casing needed, and
 * nothing is ever read from (or written back to) the wrong vault's key.
 */
export function useVaultScopedState<T>(
  cookieBase: string,
  vaultPath: string | null,
  read: (raw: string | null) => T,
  serialize: (value: T) => string
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const key = vaultScopedKey(cookieBase, vaultPath)
  const [value, setValue] = React.useState<T>(() => read(null))

  // Mirrors `key`, updated during render (not in an effect) so the write
  // effect below always targets the *current* vault's key — see its
  // comment for why the effect can't just close over `key` as a dependency.
  const keyRef = React.useRef(key)
  // eslint-disable-next-line react-hooks/refs -- mirrors key for the write effect below to read live, see its comment
  keyRef.current = key

  const prevKey = React.useRef<string | null>(null)
  React.useEffect(() => {
    if (key === prevKey.current) return
    prevKey.current = key
    setValue(read(getCookie(key)))
  }, [key, read])

  // Keyed on `value` alone, deliberately *not* also on `key` — a vault
  // switch changes `key` without changing `value` in that same commit (the
  // reseed effect above schedules that for the *next* render, unless the
  // caller resolves it synchronously itself, as app-shell's vault-switch
  // handlers do for `selectedNote`), so keying this on both would fire it
  // once with the outgoing vault's still-current `value` under the
  // incoming vault's key, stamping one vault's state onto another's.
  //
  // Skips its very first run: on mount, `value` is still `read(null)`'s
  // placeholder — the reseed effect above has already scheduled the real
  // one for the very next commit — so writing it now would overwrite
  // whatever this key's cookie already holds with that placeholder for
  // the brief window until the real value lands.
  const wroteOnce = React.useRef(false)
  React.useEffect(() => {
    if (!wroteOnce.current) {
      wroteOnce.current = true
      return
    }
    setCookie(keyRef.current, serialize(value))
  }, [value, serialize])

  return [value, setValue]
}
