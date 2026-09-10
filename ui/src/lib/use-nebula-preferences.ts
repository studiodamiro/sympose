import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import type { NebulaMode } from "@/components/sympose/knowledge-nebula-shared"

/**
 * Explore = the nebula is sharp and interactive, foreground panels give way to
 * it. Focus = it falls back to a dimmed ambient layer with no pointer
 * interaction so you can work over it (UI_DESIGN_REFERENCE.md §4).
 */
export type NebulaInteraction = "explore" | "focus"

export interface NebulaPreferences {
  /** Sharp-and-interactive vs. dimmed-ambient. Default `"focus"` (work first). */
  interaction: NebulaInteraction
  /** `"2d"` flat canvas or `"3d"` WebGL cloud. Default `"2d"`; 3D is Phase B. */
  mode: NebulaMode

  // Filters
  tags: boolean
  attachments: boolean
  existingOnly: boolean
  orphans: boolean

  // Display
  arrows: boolean
  autoRotate: boolean
  labels: boolean
  nodeSeparation: number
  nodeVividness: number
  nodeRelSize: number
  linkWidth: number
  noteDelayMs: number
  clickZoomDistance: number
  /**
   * Focus-mode scrim — how the graph is hidden behind the panels. No effect in
   * Explore.
   *   `focusBlur` — backdrop-blur radius in px (`0` = sharp).
   *   `focusTint` — matte `--background` fill opacity over it (`0` = clear,
   *   `1` = solid); reads as darkening in a dark theme, lightening in a light one.
   */
  focusBlur: number
  focusTint: number

  // Forces
  centerForce: number
  repelForce: number
  linkForce: number
  linkDistance: number
}

type Kind = "enum" | "bool" | "num"

/**
 * One declaration per knob — cookie name, kind, default — so the read and write
 * paths derive from a single source rather than two hand-kept lists (the same
 * discipline `config_schema.py` applies to backend knobs, ADR-077). Every knob
 * is persisted now; which ones the control dock actually exposes is a separate,
 * smaller list in `nebula-controls.tsx`.
 */
const SPEC: {
  [K in keyof NebulaPreferences]: {
    cookie: string
    kind: Kind
    default: NebulaPreferences[K]
  }
} = {
  interaction: { cookie: "sympose:nebula.interaction", kind: "enum", default: "focus" },
  mode: { cookie: "sympose:nebula.mode", kind: "enum", default: "2d" },
  tags: { cookie: "sympose:nebula.tags", kind: "bool", default: true },
  attachments: { cookie: "sympose:nebula.attachments", kind: "bool", default: false },
  existingOnly: { cookie: "sympose:nebula.existing_only", kind: "bool", default: false },
  orphans: { cookie: "sympose:nebula.orphans", kind: "bool", default: false },
  arrows: { cookie: "sympose:nebula.arrows", kind: "bool", default: false },
  autoRotate: { cookie: "sympose:nebula.auto_rotate", kind: "bool", default: false },
  labels: { cookie: "sympose:nebula.labels", kind: "bool", default: true },
  nodeSeparation: { cookie: "sympose:nebula.node_separation", kind: "num", default: 0 },
  nodeVividness: { cookie: "sympose:nebula.node_vividness", kind: "num", default: 0 },
  nodeRelSize: { cookie: "sympose:nebula.node_rel_size", kind: "num", default: 1.67 * 2.4 },
  linkWidth: { cookie: "sympose:nebula.link_width", kind: "num", default: 0.8 },
  noteDelayMs: { cookie: "sympose:nebula.note_delay_ms", kind: "num", default: 25 },
  clickZoomDistance: { cookie: "sympose:nebula.click_zoom_distance", kind: "num", default: 60 },
  focusBlur: { cookie: "sympose:nebula.focus_blur", kind: "num", default: 12 },
  focusTint: { cookie: "sympose:nebula.focus_tint", kind: "num", default: 0.8 },
  centerForce: { cookie: "sympose:nebula.center_force", kind: "num", default: 0.52 },
  repelForce: { cookie: "sympose:nebula.repel_force", kind: "num", default: 13.89 },
  linkForce: { cookie: "sympose:nebula.link_force", kind: "num", default: 1.0 },
  linkDistance: { cookie: "sympose:nebula.link_distance", kind: "num", default: 492 },
}

const KEYS = Object.keys(SPEC) as (keyof NebulaPreferences)[]

export const NEBULA_DEFAULTS = Object.fromEntries(
  KEYS.map((k) => [k, SPEC[k].default])
) as unknown as NebulaPreferences

function decode<K extends keyof NebulaPreferences>(
  key: K,
  raw: string | null
): NebulaPreferences[K] {
  const spec = SPEC[key]
  if (raw == null) return spec.default
  if (spec.kind === "bool") return (raw === "1") as NebulaPreferences[K]
  if (spec.kind === "num") {
    const n = Number(raw)
    return (Number.isFinite(n) ? n : spec.default) as NebulaPreferences[K]
  }
  return raw as NebulaPreferences[K]
}

function encode(kind: Kind, value: unknown): string {
  if (kind === "bool") return value ? "1" : "0"
  return String(value)
}

/**
 * Every Knowledge Nebula knob, cookie-backed per the UI-preference convention
 * (UI_DESIGN_REFERENCE.md §5) — per-browser view state, not a `config_schema.py`
 * runtime knob. Threaded from one call in the app shell the same way the editor
 * and notification preferences are, so a second hook instance can't hold a
 * divergent copy.
 */
export function useNebulaPreferences(): readonly [
  NebulaPreferences,
  <K extends keyof NebulaPreferences>(key: K, value: NebulaPreferences[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<NebulaPreferences>(() => {
    const seed = { ...NEBULA_DEFAULTS }
    for (const k of KEYS) {
      // @ts-expect-error — index write across the union is safe, decode is keyed
      seed[k] = decode(k, getCookie(SPEC[k].cookie))
    }
    return seed
  })

  const set = React.useCallback(
    <K extends keyof NebulaPreferences>(key: K, value: NebulaPreferences[K]) => {
      setCookie(SPEC[key].cookie, encode(SPEC[key].kind, value))
      setPrefs((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  return [prefs, set] as const
}
