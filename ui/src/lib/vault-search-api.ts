/**
 * Client for `GET /api/vault/search` — title/tag/content matches with
 * snippets, scoped to a persona's allowed folders. Always whole-persona-
 * scope, never narrowed to one folder — the web app derives its
 * in-folder/beyond-folder tiers by filtering this one result set
 * client-side instead of asking the backend to narrow it. Returns an
 * empty result set on any failure (offline dev, a network error, or an
 * aborted request — a newer query superseding this one) so a broken or
 * superseded search never throws into the render tree.
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
  persona: string,
  signal?: AbortSignal
): Promise<VaultSearchResult[]> {
  const params = new URLSearchParams({ q: query, persona })
  try {
    const res = await fetch(`/api/vault/search?${params}`, { signal })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as { results: VaultSearchResult[] }
    return data.results ?? []
  } catch (err) {
    if ((err as { name?: string })?.name !== "AbortError") {
      console.info(
        `[vault-search] /api/vault/search unreachable (${err}) — showing no results`
      )
    }
    return []
  }
}
