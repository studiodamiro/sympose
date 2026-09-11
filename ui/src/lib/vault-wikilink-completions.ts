import type { WikiLinkCompletion } from "@damiro/stylo"

import type { VaultNode } from "@/components/sympose"

/** Cap on returned candidates — matches the row count a `[[…` popup can show
 *  without scrolling; stylo does no filtering or re-ranking of its own. */
const MAX_CANDIDATES = 20

/** A `[[wikilink]]` target is a bare stem, e.g. "Getting Started" for
 *  "journal/Getting Started.md" — same convention `findNoteByWikilink` resolves
 *  a click against. */
function stem(name: string): string {
  return name.replace(/\.md$/i, "").trim()
}

function collectNoteStems(tree: VaultNode[], out: Set<string>): void {
  for (const node of tree) {
    if (node.type === "note") out.add(stem(node.name))
    if (node.children) collectNoteStems(node.children, out)
  }
}

/**
 * Builds a `wikiLinkSource` (stylo `>=0.7.0`) implementation off a vault tree
 * already in hand — no separate search endpoint. Candidates are every note's
 * filename stem, deduped (two folders can share a filename; the inserted
 * `[[target]]` text would be identical either way), ranked prefix-match first
 * then substring-match, both case-insensitive. An empty query returns the
 * tree's own order, capped.
 */
export function matchWikilinkTargets(
  tree: VaultNode[],
  query: string
): WikiLinkCompletion[] {
  const stems = new Set<string>()
  collectNoteStems(tree, stems)

  const q = query.trim().toLowerCase()
  const candidates = [...stems]
  const ranked = q
    ? [
        ...candidates.filter((s) => s.toLowerCase().startsWith(q)),
        ...candidates.filter(
          (s) => !s.toLowerCase().startsWith(q) && s.toLowerCase().includes(q)
        ),
      ]
    : candidates

  return ranked.slice(0, MAX_CANDIDATES).map((target) => ({ target }))
}
