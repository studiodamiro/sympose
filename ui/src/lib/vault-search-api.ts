/**
 * Client for `GET /api/vault/search` — title/tag/content matches with
 * snippets, scoped to a persona's allowed folders and optionally narrowed
 * to `folder`. Returns an empty result set on any failure (offline dev, a
 * network error) so a broken search never throws into the render tree.
 */
export interface VaultSearchResult {
  file_name: string
  rel_path: string
  match_type: "title" | "tag" | "content"
  line_no: number
  snippet: string
  title: string
  tags: string[]
  index: number
}

export async function searchVault(
  query: string,
  folder: string | undefined,
  persona: string
): Promise<VaultSearchResult[]> {
  const params = new URLSearchParams({ q: query, persona })
  if (folder) params.set("folder", folder)
  try {
    const res = await fetch(`/api/vault/search?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as { results: VaultSearchResult[] }
    return data.results ?? []
  } catch (err) {
    console.info(
      `[vault-search] /api/vault/search unreachable (${err}) — showing no results`
    )
    return []
  }
}
