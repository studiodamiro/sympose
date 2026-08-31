import * as React from "react"

import { type NebulaGraph, type NebulaNode } from "@/lib/nebula-graph"

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

/** Highlight-weighted render value for a node (matches across both renderers). */
export function nodeRenderVal(
  node: any,
  highlightedNodeIds?: Set<string>
): number {
  const isHighlight = !highlightedNodeIds || highlightedNodeIds.has(node.id)
  const base = Math.max(1.5, node.val ?? 1)
  return isHighlight ? base : base * 0.5
}
