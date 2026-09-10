import * as React from "react"

import type { NebulaGraph } from "@/lib/nebula-graph"

export interface NebulaFilterOptions {
  /** Free-text query over id / label / folder / tags. */
  query: string
  /** Whether tag hub nodes (and their links) are shown. */
  showTags: boolean
  /** Whether image / pdf / video attachment nodes are shown. */
  showAttachments: boolean
  /** Drop ghost nodes (`exists === false`). */
  existingOnly: boolean
  /** Keep zero-link notes on screen (a query match always overrides this). */
  showOrphans: boolean
  /** When set, narrow the highlight to this node and its 1-hop neighbours. */
  selectedNodeId: string | null
}

export interface NebulaFilterResult {
  /** Nodes matching the current filters — everything else renders faded. */
  highlightedNodeIds: Set<string>
  /** Nodes removed from the scene entirely (disabled tags, attachments, ghosts). */
  hiddenNodeIds: Set<string>
  /** Size of `highlightedNodeIds` — the "N active notes" readout. */
  activeCount: number
}

const ATTACHMENT_RE = /\.(png|jpg|jpeg|gif|svg|pdf|mp4|webm)$/i

/**
 * The nebula's filter derivation, lifted verbatim from the `/nebula` showcase
 * so the in-shell ambient layer and the showcase share one implementation.
 * Pure: same graph + options in, same sets out — no renderer reset, the
 * renderers just fade / cull by these sets.
 */
export function deriveNebulaFilter(
  graph: NebulaGraph,
  opts: NebulaFilterOptions
): NebulaFilterResult {
  const query = opts.query.trim().toLowerCase()
  const hidden = new Set<string>()
  let highlighted = new Set<string>()

  // Nodes that still have at least one visible edge (tag links only count when
  // tags are shown) — used for the orphan test.
  const connected = new Set<string>()
  for (const l of graph.links) {
    const src = typeof l.source === "string" ? l.source : (l.source as { id: string }).id
    const tgt = typeof l.target === "string" ? l.target : (l.target as { id: string }).id
    const isTagLink = src.startsWith("tag:") || tgt.startsWith("tag:")
    if (!isTagLink || opts.showTags) {
      connected.add(src)
      connected.add(tgt)
    }
  }

  for (const n of graph.nodes) {
    if (n.isTag && !opts.showTags) {
      hidden.add(n.id)
      continue
    }
    if (!opts.showAttachments && ATTACHMENT_RE.test(n.id)) {
      hidden.add(n.id)
      continue
    }
    if (opts.existingOnly && n.exists === false) {
      hidden.add(n.id)
      continue
    }

    // Match is computed before the orphan test so a matching disconnected note
    // can still be highlighted / framed.
    const matchesQuery =
      !query ||
      n.id.toLowerCase().includes(query) ||
      n.label.toLowerCase().includes(query) ||
      n.folder.toLowerCase().includes(query) ||
      (n.tags?.some((t) => t.toLowerCase().includes(query)) ?? false)

    const isOrphan = !connected.has(n.id) && !n.isTag
    if (!opts.showOrphans && isOrphan && !(query && matchesQuery)) continue

    if (matchesQuery) highlighted.add(n.id)
  }

  // A selected node narrows the highlight to it + its direct neighbours.
  if (opts.selectedNodeId) {
    const neighbours = new Set<string>([opts.selectedNodeId])
    for (const l of graph.links) {
      const src = typeof l.source === "string" ? l.source : (l.source as { id: string }).id
      const tgt = typeof l.target === "string" ? l.target : (l.target as { id: string }).id
      if (src === opts.selectedNodeId) neighbours.add(tgt)
      if (tgt === opts.selectedNodeId) neighbours.add(src)
    }
    const focused = new Set<string>()
    for (const id of highlighted) if (neighbours.has(id)) focused.add(id)
    highlighted = focused
  }

  return {
    highlightedNodeIds: highlighted,
    hiddenNodeIds: hidden,
    activeCount: highlighted.size,
  }
}

/** `deriveNebulaFilter` memoised on the graph and each option. */
export function useNebulaFilter(
  graph: NebulaGraph,
  opts: NebulaFilterOptions
): NebulaFilterResult {
  const { query, showTags, showAttachments, existingOnly, showOrphans, selectedNodeId } = opts
  return React.useMemo(
    () =>
      deriveNebulaFilter(graph, {
        query,
        showTags,
        showAttachments,
        existingOnly,
        showOrphans,
        selectedNodeId,
      }),
    [graph, query, showTags, showAttachments, existingOnly, showOrphans, selectedNodeId]
  )
}
