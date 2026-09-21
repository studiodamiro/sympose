import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

/** `"sympose"` — the fixed product wordmark (default). `"vault"` — the
 *  active vault's name, truncated when it's long. */
export type BrandMarkLabel = "sympose" | "vault"

const COOKIE = "sympose:brand_mark_label"
const DEFAULT: BrandMarkLabel = "sympose"

/**
 * What the brand-mark wordmark shows, next to the workspace-switcher trigger
 * in `<TopBar>` and `<MainMenu>`. Cookie-backed per-browser view preference,
 * same convention as the editor / notification / nebula knobs — not backend
 * config, since it's purely how this browser likes the chrome to read.
 */
export function useBrandMarkLabel(): readonly [
  BrandMarkLabel,
  (value: BrandMarkLabel) => void,
] {
  const [label, setLabelState] = React.useState<BrandMarkLabel>(() =>
    getCookie(COOKIE) === "vault" ? "vault" : DEFAULT
  )

  const setLabel = React.useCallback((value: BrandMarkLabel) => {
    setLabelState(value)
    setCookie(COOKIE, value)
  }, [])

  return [label, setLabel] as const
}
