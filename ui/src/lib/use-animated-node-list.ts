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
 * of vanishing the instant a vault refetch (a delete-to-bin, a
 * rename that moves a note out of this list, etc.) comes back without it.
 * Entrance is already handled by the row itself mounting fresh
 * with `animate-in` — this hook only needs to cover the removal half.
 *
 * No fixed exit duration is tracked here: the caller drives the exit
 * animation with CSS (`duration-thumb`) and reports completion via
 * `onExitComplete` from the row's own `onAnimationEnd`, so this hook can't
 * drift out of sync with whatever duration the CSS actually uses.
 *
 * Order: nodes still present keep their live data; closing nodes keep their
 * last-known position and content. Genuinely new nodes are appended in
 * `nodes`' own order — their exact position during the brief overlap with a
 * closing sibling doesn't matter since they animate in independently.
 */
export function useAnimatedNodeList(nodes: VaultNode[]) {
  // `prevNodes` + the render-time comparison below is React's documented
  // "adjust state during render" pattern — it replaces an effect that ran
  // setDisplay after the fact, so a nodes change lands in the same render
  // pass instead of an extra effect-triggered re-render.
  const [prevNodes, setPrevNodes] = React.useState(nodes)
  const [display, setDisplay] = React.useState<AnimatedNodeEntry[]>(() =>
    nodes.map((node) => ({ node, closing: false }))
  )

  if (nodes !== prevNodes) {
    setPrevNodes(nodes)

    const byPath = new Map(nodes.map((node) => [node.path, node]))
    const placed = new Set<string>()
    const merged: AnimatedNodeEntry[] = []
    // `nodes` can arrive as a fresh array/object graph on every render (an
    // unmemoized `.map()`/`.filter()` upstream) without any node actually
    // being added, removed, or replaced with different data — `changed`
    // tracks whether that's actually happened, so `display` can keep the
    // same reference when it hasn't.
    let changed = display.length !== nodes.length

    for (const entry of display) {
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

    if (changed) setDisplay(merged)
  }

  const onExitComplete = React.useCallback((path: string) => {
    setDisplay((prev) =>
      prev.filter((entry) => !(entry.node.path === path && entry.closing))
    )
  }, [])

  return { display, onExitComplete }
}
