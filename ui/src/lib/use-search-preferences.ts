import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

export interface SearchPreferences {
  /** Whether the vault search field also matches notes outside the folder
   *  currently in view (the merged "N matches beyond X" list, below the
   *  folder's own results). Default on. */
  beyondFolder: boolean
  /** How many "beyond X" results are shown per page. Default 10. */
  resultsPerPage: number
}

type Kind = "bool" | "num"

/**
 * One declaration per knob — cookie name, kind, default — so the read and
 * write paths derive from a single source rather than two hand-kept lists,
 * same discipline as `use-nebula-preferences.ts` (itself mirroring
 * `config_schema.py`'s "declared once", ADR-077, for backend knobs).
 */
const SPEC: {
  [K in keyof SearchPreferences]: {
    cookie: string
    kind: Kind
    default: SearchPreferences[K]
  }
} = {
  beyondFolder: { cookie: "sympose:search.beyond_folder", kind: "bool", default: true },
  resultsPerPage: { cookie: "sympose:search.results_per_page", kind: "num", default: 10 },
}

const KEYS = Object.keys(SPEC) as (keyof SearchPreferences)[]

export const SEARCH_DEFAULTS = Object.fromEntries(
  KEYS.map((k) => [k, SPEC[k].default])
) as unknown as SearchPreferences

function decode<K extends keyof SearchPreferences>(
  key: K,
  raw: string | null
): SearchPreferences[K] {
  const spec = SPEC[key]
  if (raw == null) return spec.default
  if (spec.kind === "bool") return (raw === "1") as SearchPreferences[K]
  const n = Number(raw)
  return (Number.isFinite(n) && n > 0 ? n : spec.default) as SearchPreferences[K]
}

function encode(kind: Kind, value: unknown): string {
  if (kind === "bool") return value ? "1" : "0"
  return String(value)
}

/**
 * Vault search knobs, cookie-backed per the UI-preference convention
 * (per-browser view state, not a `config_schema.py` runtime knob). Threaded
 * from one call in the app shell the same way the editor/notification/nebula
 * preferences are, so a second hook instance can't hold a divergent copy.
 */
export function useSearchPreferences(): readonly [
  SearchPreferences,
  <K extends keyof SearchPreferences>(key: K, value: SearchPreferences[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<SearchPreferences>(() => {
    const seed = { ...SEARCH_DEFAULTS }
    for (const k of KEYS) {
      // @ts-expect-error — index write across the union is safe, decode is keyed
      seed[k] = decode(k, getCookie(SPEC[k].cookie))
    }
    return seed
  })

  const set = React.useCallback(
    <K extends keyof SearchPreferences>(key: K, value: SearchPreferences[K]) => {
      setCookie(SPEC[key].cookie, encode(SPEC[key].kind, value))
      setPrefs((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  return [prefs, set] as const
}
