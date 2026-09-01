import * as React from "react"

import {
  nodeColor,
  type NebulaGraph,
  type NebulaNode,
} from "@/lib/nebula-graph"

/**
 * Shared contract + helpers for the Knowledge Nebula renderers. Module A of the
 * wiki spec ships in two skins driven by the `mode` prop:
 *
 *  - `"3d"` — a force-directed WebGL cloud (`react-force-graph-3d` / three.js).
 *  - `"2d"` — the flat Obsidian-style canvas graph (`react-force-graph-2d`).
 *
 * Both implement {@link KnowledgeNebulaHandle} and accept
 * {@link KnowledgeNebulaProps}, so `<KnowledgeNebula>` can swap between them
 * without the consumer noticing. `graph` is a plain `NebulaGraph` — the same
 * shape as the future `GET /api/vault/graph` response.
 */
export type NebulaMode = "2d" | "3d"

export interface KnowledgeNebulaHandle {
  /** Frame the whole graph. */
  zoomToFit: (duration?: number, padding?: number) => void
  /** Staggered "birth" reveal — notes pop in one by one, `noteDelayMs` apart. */
  animateBirth: (noteDelayMs?: number) => void
  /** Fly to a node and frame it with its 1-hop neighbours. */
  focusNode: (
    nodeOrId: NebulaNode | string,
    distance?: number,
    duration?: number
  ) => void
  /** Frame an arbitrary set of nodes (e.g. current search matches). */
  fitNodes: (
    nodeIds: string[] | Set<string>,
    duration?: number,
    padding?: number
  ) => void
}

export interface KnowledgeNebulaProps {
  /** Graph feed — same shape as the future `/api/vault/graph` response. */
  graph: NebulaGraph
  className?: string
  /** `"3d"` WebGL cloud (default) or `"2d"` Obsidian-style flat canvas graph. */
  mode?: NebulaMode
  /**
   * Focus / Chat Mode: fade the cloud back, drop pointer interaction, and (3D
   * only) let the camera drift in a slow auto-orbit so it reads as ambient
   * motion rather than a live tool. Default `false` (Explore Mode).
   */
  dimmed?: boolean
  /**
   * Whether orbit / zoom / drag are live. Mirrors `pointer-events`. Defaults to
   * the opposite of `dimmed`; pass explicitly to override.
   */
  interactive?: boolean
  /** Whether light theme contrast colors should be applied to nodes and links. */
  isLight?: boolean
  /** Auto rotate the camera around the graph. 3D only — ignored in 2D. */
  autoRotate?: boolean
  /**
   * Draw node title labels in the scene. Both renderers gate them so they only
   * appear when you get close: by zoom (`globalScale`) in 2D, by camera
   * distance in 3D. Default `true`.
   */
  showLabels?: boolean
  /** Set of node IDs that match current filters (unmatched nodes are faded). */
  highlightedNodeIds?: Set<string>
  /** Set of node IDs that should be completely hidden (e.g. disabled tags). */
  hiddenNodeIds?: Set<string>
  /** Closeness knob for node-click framing (default 60; lower = closer). */
  clickZoomDistance?: number
  /** Node relative size multiplier (default 4). */
  nodeRelSize?: number
  /**
   * Signed knob that shifts node folder colours relative to the background.
   * Positive pushes them away for contrast (toward black in light mode, toward
   * white in dark mode); negative pulls them toward the background so they read
   * softer. `0` = palette as-is; `±1` = fully black / white. Default `0`.
   */
  nodeSeparation?: number
  /**
   * Signed saturation knob for node folder colours. Positive makes the hue pop,
   * negative fades it toward grey. `0` = palette as-is; `-1` = greyscale,
   * `+1` = fully saturated. Default `0`.
   */
  nodeVividness?: number
  /** Link line width (falls back to a per-theme default). */
  linkWidth?: number
  /** Number of animated link directional particles per edge (default 0). */
  linkParticles?: number
  /** Render directional arrow heads on link lines. */
  showArrows?: boolean
  /** Repel force strength (d3 charge). */
  repelForce?: number
  /** Link distance. */
  linkDistance?: number
  /** Link force strength. */
  linkForce?: number
  /** Center force strength. */
  centerForce?: number
  /** Fired with the vault node when a node is clicked. */
  onNodeClick?: (node: NebulaNode) => void
  /** Fired when the background canvas is clicked. */
  onBackgroundClick?: () => void
}

/** Live pixel size of `ref`'s element, tracked via `ResizeObserver`. */
export function useElementSize(ref: React.RefObject<HTMLElement | null>) {
  const [size, setSize] = React.useState({ w: 0, h: 0 })
  React.useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ w: Math.round(width), h: Math.round(height) })
    })
    ro.observe(el)
    const r = el.getBoundingClientRect()
    setSize({ w: Math.round(r.width), h: Math.round(r.height) })
    return () => ro.disconnect()
  }, [ref])
  return size
}

/** Build the hover-tooltip HTML string renderer for the given theme. */
export function createNodeTooltip(isLight: boolean) {
  return (node: any): string => {
    const n = node as NebulaNode
    const home = n.folder || "unresolved link"
    const tags = n.tags?.length ? ` · #${n.tags.join(" #")}` : ""
    const bg = isLight ? "rgba(255,255,255,0.96)" : "rgba(20,22,28,0.92)"
    const fg = isLight ? "#0f172a" : "#e7e9ee"
    const border = isLight ? "rgba(0,0,0,0.12)" : "rgba(255,255,255,0.12)"

    return (
      `<div style="font:12px/1.4 'Inter Variable',sans-serif;padding:4px 8px;` +
      `border-radius:6px;background:${bg};color:${fg};` +
      `border:1px solid ${border};box-shadow:0 4px 12px rgba(0,0,0,0.15)">` +
      `<strong>${n.label}</strong><span style="opacity:.65"> · ${home}${tags}</span></div>`
    )
  }
}

/** Clamp `v` into `[lo, hi]`. */
export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/**
 * Linear-blend a `#rrggbb` colour toward `target` (also `#rrggbb`). `amount`
 * 0 = unchanged, 1 = fully `target`. Non-hex inputs pass through untouched.
 */
export function blendHex(hex: string, target: string, amount: number): string {
  const a = clamp(amount, 0, 1)
  const re = /^#[0-9a-fA-F]{6}$/
  if (a <= 0 || !re.test(hex) || !re.test(target)) return hex
  const ch = (i: number) => {
    const from = parseInt(hex.slice(i, i + 2), 16)
    const to = parseInt(target.slice(i, i + 2), 16)
    return Math.round(from + (to - from) * a)
      .toString(16)
      .padStart(2, "0")
  }
  return `#${ch(1)}${ch(3)}${ch(5)}`
}

function hexToHsl(hex: string): [number, number, number] | null {
  const m = /^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(hex)
  if (!m) return null
  const r = parseInt(m[1], 16) / 255
  const g = parseInt(m[2], 16) / 255
  const b = parseInt(m[3], 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  const d = max - min
  if (d === 0) return [0, 0, l]
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
  else if (max === g) h = (b - r) / d + 2
  else h = (r - g) / d + 4
  return [h / 6, s, l]
}

function hslToHex(h: number, s: number, l: number): string {
  const hue = (p: number, q: number, t: number) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }
  let r: number
  let g: number
  let b: number
  if (s === 0) {
    r = g = b = l
  } else {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s
    const p = 2 * l - q
    r = hue(p, q, h + 1 / 3)
    g = hue(p, q, h)
    b = hue(p, q, h - 1 / 3)
  }
  const to = (v: number) =>
    Math.round(clamp(v, 0, 1) * 255)
      .toString(16)
      .padStart(2, "0")
  return `#${to(r)}${to(g)}${to(b)}`
}

/**
 * Scale a `#rrggbb` colour's HSL saturation. `amount` in `[-1, 1]`: `0` =
 * unchanged, `-1` = greyscale, `+1` = fully saturated. Non-hex passes through.
 */
export function adjustSaturation(hex: string, amount: number): string {
  const a = clamp(amount, -1, 1)
  if (a === 0) return hex
  const hsl = hexToHsl(hex)
  if (!hsl) return hex
  const [h, s, l] = hsl
  const next = a < 0 ? s * (1 + a) : s + (1 - s) * a
  return hslToHex(h, clamp(next, 0, 1), l)
}

/**
 * Folder colour for a node with the two signed colour knobs applied:
 * {@link KnowledgeNebulaProps.nodeVividness} scales saturation first, then
 * {@link KnowledgeNebulaProps.nodeSeparation} blends the result away from the
 * background (black in light mode, white in dark) when positive, or toward it
 * when negative. Both `0` leaves the palette untouched.
 */
export function nebulaNodeColor(
  node: any,
  isLight: boolean,
  separation = 0,
  vividness = 0
): string {
  let color = nodeColor(node as NebulaNode, isLight)
  if (vividness) color = adjustSaturation(color, vividness)
  if (separation) {
    const awayFromBg = isLight ? "#000000" : "#ffffff"
    const towardBg = isLight ? "#ffffff" : "#000000"
    color = blendHex(
      color,
      separation >= 0 ? awayFromBg : towardBg,
      Math.abs(separation)
    )
  }
  return color
}

/** Highlight-weighted render value for a node (matches across both renderers). */
export function nodeRenderVal(
  node: any,
  highlightedNodeIds?: Set<string>
): number {
  const isHighlight = !highlightedNodeIds || highlightedNodeIds.has(node.id)
  const base = Math.max(1.5, node.val ?? 1)
  return isHighlight ? base : base * 0.5
}
