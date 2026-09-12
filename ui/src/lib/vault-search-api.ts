/**
 * Client for `GET /api/vault/search` — the dashboard search field's content
 * tier (ADR-057 structured results), behind the instant client-side tree
 * filter (`filterTreeByQuery`). Returns `[]` when the backend is unreachable
 * (offline dev) or the request is aborted (a newer query superseded it) so
 * the caller never has to special-case those.
 */
export interface VaultSearchMatch {
  file_name: string
  rel_path: string
  match_type: "title" | "tag" | "content"
  line_no: number
  snippet: string
  title: string
  tags: string[]
}

export async function fetchVaultSearch(
  query: string,
  persona: string,
  signal?: AbortSignal
): Promise<VaultSearchMatch[]> {
  try {
    const res = await fetch(
      `/api/vault/search?q=${encodeURIComponent(query)}&persona=${encodeURIComponent(persona)}`,
      { signal }
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as { results: VaultSearchMatch[] }
    return data.results ?? []
  } catch (err) {
    if ((err as { name?: string })?.name === "AbortError") return []
    console.info(
      `[vault-search] /api/vault/search unreachable (${err}) — no content matches`
    )
    return []
  }
}
