/**
 * Minimal cookie helpers for persisting user-interface preferences (resizable
 * panel widths, etc.). Cookies, not localStorage, are the store for these.
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

/** Deterministic short hash (FNV-1a, 32-bit) of a string, for turning a
 *  filesystem path into a cookie-name-safe suffix — cookie names can't
 *  reliably hold `/`, `~`, spaces, and so on. Collision risk is irrelevant
 *  at "a handful of configured vaults per user" scale. */
function hashKey(input: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0).toString(36)
}

/**
 * A cookie base name scoped to one vault (by its absolute path) — so
 * per-vault state (the open note, recent notes, pinned notes) doesn't leak
 * across a vault switch, while pure layout/UI preferences (panel widths,
 * which Settings section is open, ...) stay on their own unscoped keys.
 * `vaultPath` of `null` (no vault configured) falls back to the bare
 * `base`, matching pre-multi-vault behavior.
 */
export function vaultScopedKey(base: string, vaultPath: string | null): string {
  return vaultPath ? `${base}:${hashKey(vaultPath)}` : base
}
