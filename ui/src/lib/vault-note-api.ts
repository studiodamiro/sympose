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

export type CreateVaultNoteResult =
  | { ok: true; path: string }
  | { ok: false; error: string }

/**
 * Client for `POST /api/vault/note` — create a new note at `path` (relative to
 * the vault, e.g. `Projects/Idea`). The backend seeds a frontmatter + title
 * stub. A 409 means a note already exists there, a 403 that the path is outside
 * the persona's sandbox (ADR-083).
 */
export async function createVaultNote(
  path: string,
  persona: string
): Promise<CreateVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, persona }),
    })
    if (res.ok) return { ok: true, path }
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => undefined)
    return { ok: false, error: detail || `Couldn't create note (HTTP ${res.status})` }
  } catch (err) {
    return { ok: false, error: `Couldn't create note — backend unreachable (${err})` }
  }
}

async function detailOf(res: Response): Promise<string | undefined> {
  return res
    .json()
    .then((b) => (b as { detail?: string }).detail)
    .catch(() => undefined)
}

export type RenameVaultNoteResult =
  | { ok: true; path: string; detail: string }
  | { ok: false; error: string }

/**
 * Client for `PATCH /api/vault/note` — rename `path` to `newName` (a bare stem
 * stays in the same folder) and rewrite the `[[wikilinks]]` that referenced it
 * (ADR-084). 404 source gone, 409 target taken, 403 outside the sandbox.
 * `path` in the result is the note's new vault-relative path.
 */
export async function renameVaultNote(
  path: string,
  newName: string,
  persona: string
): Promise<RenameVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, new_path: newName, persona }),
    })
    if (res.ok) {
      const body = (await res.json()) as { path: string; detail: string }
      return { ok: true, path: body.path, detail: body.detail }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `Rename failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Rename failed — backend unreachable (${err})` }
  }
}

export type DeleteVaultNoteResult =
  | { ok: true; detail: string }
  | { ok: false; error: string }

/**
 * Client for `DELETE /api/vault/note` — move the note to `<vault>/.trash/`
 * (ADR-084). 404 if it's already gone, 403 outside the sandbox.
 */
export async function deleteVaultNote(
  path: string,
  persona: string
): Promise<DeleteVaultNoteResult> {
  try {
    const res = await fetch(
      `/api/vault/note?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`,
      { method: "DELETE" }
    )
    if (res.ok) {
      const body = (await res.json()) as { detail: string }
      return { ok: true, detail: body.detail }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `Delete failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Delete failed — backend unreachable (${err})` }
  }
}
