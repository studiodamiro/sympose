import * as React from "react"

import type { VaultNode } from "@/components/sympose/vault-tree"

export interface AnimatedNodeEntry {
  node: VaultNode
  /** This node just dropped out of `nodes` — still mounted so it can play
   *  an exit animation before the caller removes it via `onExitComplete`. */
  closing: boolean
}

/**
 * Keeps a deleted row mounted long enough to play an exit animation instead
 * of vanishing the instant a vault refetch (ADR-099's delete-to-bin, a
 * rename that moves a note out of this list, etc.) comes back without it
 * (ADR-103). Entrance is already handled by the row itself mounting fresh
 * with `animate-in` — this hook only needs to cover the removal half.
 *
 * No fixed exit duration is tracked here: the caller drives the exit
 * animation with CSS (`duration-thumb`, ADR-102) and reports completion via
 * `onExitComplete` from the row's own `onAnimationEnd`, so this hook can't
 * drift out of sync with whatever duration the CSS actually uses.
 *
 * Order: nodes still present keep their live data; closing nodes keep their
 * last-known position and content. Genuinely new nodes are appended in
 * `nodes`' own order — their exact position during the brief overlap with a
 * closing sibling doesn't matter since they animate in independently.
 */
export function useAnimatedNodeList(nodes: VaultNode[]) {
  const [display, setDisplay] = React.useState<AnimatedNodeEntry[]>(() =>
    nodes.map((node) => ({ node, closing: false }))
  )

  React.useEffect(() => {
    const byPath = new Map(nodes.map((node) => [node.path, node]))

    setDisplay((prev) => {
      const placed = new Set<string>()
      const merged: AnimatedNodeEntry[] = []
      let changed = prev.length !== nodes.length

      for (const entry of prev) {
        const fresh = byPath.get(entry.node.path)
        if (fresh) {
          if (fresh !== entry.node || entry.closing) changed = true
          merged.push({ node: fresh, closing: false })
          placed.add(entry.node.path)
        } else if (entry.closing) {
          merged.push(entry)
        } else {
          changed = true
          merged.push({ node: entry.node, closing: true })
        }
      }

      for (const node of nodes) {
        if (!placed.has(node.path)) {
          changed = true
          merged.push({ node, closing: false })
        }
      }

      // Bail out with the same reference when nothing actually changed —
      // `nodes` can arrive as a fresh array/object graph on every render
      // (an unmemoized `.map()`/`.filter()` upstream) without any node
      // actually being added, removed, or replaced with different data.
      return changed ? merged : prev
    })
  }, [nodes])

  const onExitComplete = React.useCallback((path: string) => {
    setDisplay((prev) =>
      prev.filter((entry) => !(entry.node.path === path && entry.closing))
    )
  }, [])

  return { display, onExitComplete }
}
