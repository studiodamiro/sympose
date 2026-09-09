export interface VaultNote {
  path: string
  content: string
}

/**
 * Client for `GET /api/vault/note` — the raw Markdown (frontmatter included)
 * for one vault file, scoped to a persona's allowed vault folders. Returns
 * `null` on a 404 (note missing) or when the backend is unreachable (offline
 * dev), so the caller renders an empty/error state instead of throwing.
 */
export async function fetchVaultNote(
  path: string,
  persona: string
): Promise<VaultNote | null> {
  try {
    const res = await fetch(
      `/api/vault/note?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as VaultNote
  } catch (err) {
    console.info(`[vault-note] /api/vault/note unreachable (${err})`)
    return null
  }
}
