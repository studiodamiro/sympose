/**
 * Minimal cookie helpers for persisting user-interface preferences (resizable
 * panel widths, etc.) — see UI_DESIGN_REFERENCE.md §5. Cookies, not
 * localStorage, are the store for these.
 */

export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null
  const escaped = name.replace(/([.*+?^${}()|[\]\\])/g, "\\$1")
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${escaped}=([^;]*)`)
  )
  return match ? decodeURIComponent(match[1]) : null
}

export function setCookie(name: string, value: string, days = 365): void {
  if (typeof document === "undefined") return
  const maxAge = Math.floor(days * 86400)
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; SameSite=Lax`
}

/** Read a cookie as a finite number, or `null` if absent / unparseable. */
export function getCookieNumber(name: string): number | null {
  const raw = getCookie(name)
  if (raw == null) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

/** Read a cookie as a boolean (`"1"` / `"0"`); `fallback` when absent. */
export function getCookieBool(name: string, fallback: boolean): boolean {
  const raw = getCookie(name)
  if (raw == null) return fallback
  return raw === "1"
}

/** Persist a boolean as `"1"` / `"0"`. */
export function setCookieBool(name: string, value: boolean, days = 365): void {
  setCookie(name, value ? "1" : "0", days)
}
