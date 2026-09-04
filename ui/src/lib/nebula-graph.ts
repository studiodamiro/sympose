/**
 * Client shape of the `GET /api/vault/graph` contract
 * (docs/UI_DESIGN_REFERENCE.md §9, wiki spec §2 Module A). Vault notes are
 * nodes, `[[wikilinks]]` are links. The endpoint does not exist yet — until it
 * does, `mock-nebula.json` stands in as the feed, and swapping to the real
 * source is a one-line `fetch()` in whoever owns the data.
 */
export interface NebulaNode {
  /** Vault-relative stem, unique across the graph — e.g. `"Architecture"`. */
  id: string
  /** Display label; usually identical to `id`. */
  label: string
  /**
   * Top-level vault folder the note lives under (`"Projects"`, `"Code"`, …).
   * Empty string for a ghost node (see `exists`). Drives the colour group.
   */
  folder: string
  /** Frontmatter tags, without the leading `#`. */
  tags: string[]
  /** Degree weight — forward links + backlinks + 1. Scales the node's radius. */
  val: number
  /** Whether this node represents a hashtag node. */
  isTag?: boolean
  /**
   * `false` when this id is only ever a `[[wikilink]]` target with no file on
   * disk yet. Omitted (treated as `true`) for real notes. The "Existing files
   * only" filter drops these.
   */
  exists?: boolean
}

export interface NebulaLink {
  /** Source node id, or — after force-graph has processed the graph — the node. */
  source: string
  /** Target node id, or the resolved node object. */
  target: string
}

export interface NebulaGraph {
  nodes: NebulaNode[]
  links: NebulaLink[]
}

/**
 * Folder-domain colours for the nebula, keyed by the names in
 * `VAULT_FOLDERS`. Hex rather than the app's `oklch()` tokens because the
 * values are handed straight to `THREE.Color`, whose CSS parser is limited to
 * named / hex / `rgb()`. Tuned to read as distinct points of light on a dark
 * canvas (the nebula is a dark-surface visualization per the spec).
 */
export const FOLDER_COLORS: Record<string, string> = {
  Projects: "#56c9e0", // cyan
  Code: "#6fdcb0", // mint
  Daily: "#e7c14a", // amber
  Drawings: "#b98cff", // violet
  General: "#9aa7bd", // slate
  Limbo: "#6b7280", // dim grey
  Movies: "#f2889b", // rose
  People: "#f0a35a", // orange
  Quotes: "#d9c169", // gold
  Reading: "#7aa7e0", // blue
  Recipes: "#e78a5c", // terracotta
  Templates: "#5fc7c7", // teal
  Writing: "#e07ac0", // magenta
  Tags: "#10b981", // emerald green for hashtags
}

/** Saturated, high-contrast jewel tones for bright/light backgrounds. */
export const FOLDER_COLORS_LIGHT: Record<string, string> = {
  Projects: "#0284c7", // deep sky blue
  Code: "#059669", // deep emerald
  Daily: "#b45309", // deep bronze/amber
  Drawings: "#7c3aed", // deep violet
  General: "#334155", // deep slate
  Limbo: "#475569", // charcoal grey
  Movies: "#be123c", // deep rose
  People: "#c2410c", // deep burnt orange
  Quotes: "#92400e", // deep gold/brown
  Reading: "#1d4ed8", // deep royal blue
  Recipes: "#b45309", // deep terracotta
  Templates: "#0f766e", // deep teal
  Writing: "#a21caf", // deep magenta
  Tags: "#047857", // deep emerald green for hashtags
}

/** Fallback for an unknown folder. */
const UNKNOWN_FOLDER_COLOR = "#8b93a7"
const UNKNOWN_FOLDER_COLOR_LIGHT = "#334155"
/** Ghost nodes (unresolved wikilink targets) read as faint outlines. */
const GHOST_COLOR = "#4b5563"
const GHOST_COLOR_LIGHT = "#94a3b8"

/** Resolve a node's render colour from its folder / existence and active theme. */
export function nodeColor(node: NebulaNode, isLight = false): string {
  if (isLight) {
    if (node.exists === false) return GHOST_COLOR_LIGHT
    return FOLDER_COLORS_LIGHT[node.folder] ?? UNKNOWN_FOLDER_COLOR_LIGHT
  }
  if (node.exists === false) return GHOST_COLOR
  return FOLDER_COLORS[node.folder] ?? UNKNOWN_FOLDER_COLOR
}

/** Distinct folders present in a graph, in `VAULT_FOLDERS`-ish display order. */
export function foldersInGraph(graph: NebulaGraph): string[] {
  const seen = new Set<string>()
  for (const n of graph.nodes) if (n.folder) seen.add(n.folder)
  return Object.keys(FOLDER_COLORS).filter((f) => seen.has(f))
}
