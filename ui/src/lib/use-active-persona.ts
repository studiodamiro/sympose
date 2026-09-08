import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

const COOKIE = "sympose:active_persona"
const DEFAULT_HANDLE = "samantha"

/**
 * The dashboard's active persona — the handle every `?persona=` scoped request
 * (vault tree, note reads, backlinks) is made against. Persisted to a cookie,
 * not localStorage, per the UI-preference convention (UI_DESIGN_REFERENCE.md
 * §5). There is no server-side dashboard session: the picker is client state.
 */
export function useActivePersona(): readonly [
  string,
  (handle: string) => void,
] {
  const [handle, setHandleState] = React.useState<string>(
    () => getCookie(COOKIE) || DEFAULT_HANDLE
  )

  const setHandle = React.useCallback((next: string) => {
    const clean = next.replace(/^@/, "").toLowerCase().trim() || DEFAULT_HANDLE
    setHandleState(clean)
    setCookie(COOKIE, clean)
  }, [])

  return [handle, setHandle] as const
}
