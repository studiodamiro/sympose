/**
 * `[[target]]` / `[[target|label]]` outbound targets in a note body, deduped
 * and in first-seen order. Mirrors the pattern stylo scans the in-place canvas
 * with (`src/wikilink.ts`) — kept separate since stylo doesn't export it, but
 * the two must stay in sync if that shape ever changes.
 */
export function extractWikilinks(markdown: string): string[] {
  const pattern = /\[\[([^\]|\n]+?)(?:\|([^\]\n]+?))?\]\]/g
  const seen = new Set<string>()
  for (const match of markdown.matchAll(pattern)) {
    const target = match[1]?.trim()
    if (target) seen.add(target)
  }
  return [...seen]
}

/**
 * Parses a value that is *entirely* a `[[target]]` / `[[target|label]]`
 * wikilink — anchored start-to-end, unlike `extractWikilinks` which scans for
 * any number embedded in running text. Used for frontmatter fields (e.g. an
 * Obsidian `up: ["[[Parent note]]"]` relation), where a field's whole value is
 * the link rather than prose containing one. `null` if it isn't (only) a link.
 */
export function parseWikilink(value: string): { target: string; label: string } | null {
  const match = /^\[\[([^\]|\n]+?)(?:\|([^\]\n]+?))?\]\]$/.exec(value.trim())
  const target = match?.[1]?.trim()
  if (!target) return null
  return { target, label: match?.[2]?.trim() || target }
}
