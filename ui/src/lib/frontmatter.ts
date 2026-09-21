import { parse, stringify } from "yaml"

export type FrontmatterScalar = string | number | boolean | null
export type FrontmatterData = Record<string, FrontmatterScalar | FrontmatterScalar[]>

/**
 * Parses the inner text of a note's `---`…`---` block (as returned by
 * stylo's `splitFrontmatter`) into a plain object. `null` for anything that
 * isn't a flat YAML mapping — a scalar document, a list, or invalid YAML —
 * so the card can fall back to leaving it alone rather than guessing.
 */
export function parseFrontmatter(raw: string): FrontmatterData | null {
  if (!raw.trim()) return {}
  let data: unknown
  try {
    data = parse(raw)
  } catch {
    return null
  }
  if (data === null || data === undefined) return {}
  if (typeof data !== "object" || Array.isArray(data)) return null
  return data as FrontmatterData
}

/** Serializes frontmatter fields back to the raw inner-block text `yaml.parse` round-trips from. */
export function serializeFrontmatter(data: FrontmatterData): string {
  if (Object.keys(data).length === 0) return ""
  return stringify(data).trimEnd()
}
