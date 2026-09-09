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

export type SaveVaultNoteResult =
  | { ok: true }
  | { ok: false; error: string }

/**
 * Client for `PUT /api/vault/note` — write the editor's full Markdown (with
 * frontmatter) back to an existing vault note. The backend never creates a new
 * file: a 404 means the note is gone, a 403 that the path fell outside the
 * persona's sandbox (ADR-081). Returns a discriminated result rather than
 * throwing so the caller can toast the message.
 */
export async function saveVaultNote(
  path: string,
  content: string,
  persona: string
): Promise<SaveVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content, persona }),
    })
    if (res.ok) return { ok: true }
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => undefined)
    return { ok: false, error: detail || `Save failed (HTTP ${res.status})` }
  } catch (err) {
    return { ok: false, error: `Save failed — backend unreachable (${err})` }
  }
}
