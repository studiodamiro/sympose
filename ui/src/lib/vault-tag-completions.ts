import type { TagCompletion } from "@damiro/stylo"

import type { NebulaGraph } from "@/lib/nebula-graph"

/** Cap on returned candidates — matches `matchWikilinkTargets`' popup-row budget. */
const MAX_CANDIDATES = 20

/**
 * Builds a `tagSource` (stylo `>=0.12.0`) implementation off the Knowledge
 * Nebula's master graph — no separate tag scan. `buildMasterGraph` already
 * pre-indexes every distinct frontmatter tag as a `tag:<name>` hub node
 * (`nebula-graph.ts`), so this just reads that index back out rather than
 * walking notes itself. Ranked prefix-match first then substring-match, both
 * case-insensitive, same as the wikilink source; an empty query returns the
 * graph's own (first-seen) order, capped.
 */
export function matchTagTargets(graph: NebulaGraph, query: string): TagCompletion[] {
  const tags = graph.nodes.filter((n) => n.isTag).map((n) => n.tags[0])

  const q = query.trim().toLowerCase()
  const ranked = q
    ? [
        ...tags.filter((t) => t.toLowerCase().startsWith(q)),
        ...tags.filter((t) => !t.toLowerCase().startsWith(q) && t.toLowerCase().includes(q)),
      ]
    : tags

  return ranked.slice(0, MAX_CANDIDATES).map((tag) => ({ tag }))
}
