/**
 * Clients for `/api/vault/trash*` — the note-recovery surface (ADR-085).
 * `VaultManager.delete_note` moves a note to `<vault>/.trash/` rather than
 * unlinking it; these list what's recoverable, put one back, or delete it for
 * good. Same discriminated-result shape as `vault-note-api.ts` so callers can
 * toast the message instead of catching.
 */

export interface TrashedNote {
  /** `.trash`-relative path — the handle for restore / purge. */
  trash_path: string
  /** Where the note lived before deletion (clash suffix already stripped). */
  original_path: string
  /** Epoch seconds of the deletion (the trashed file's mtime). */
  deleted_at: number
  size: number
}

async function detailOf(res: Response): Promise<string | undefined> {
  return res
    .json()
    .then((b) => (b as { detail?: string }).detail)
    .catch(() => undefined)
}

/**
 * `GET /api/vault/trash` — recoverable notes for this persona, newest deletion
 * first. Returns `[]` on any error so the caller renders an empty state.
 */
export async function fetchTrash(persona: string): Promise<TrashedNote[]> {
  try {
    const res = await fetch(
      `/api/vault/trash?persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = (await res.json()) as { items: TrashedNote[] }
    return body.items ?? []
  } catch (err) {
    console.info(`[vault-trash] /api/vault/trash unreachable (${err})`)
    return []
  }
}

export type TrashMutationResult =
  { ok: true; detail: string } | { ok: false; error: string }

/**
 * `POST /api/vault/trash/restore` — move the trashed note back to its original
 * path. 404 not in trash, 409 something occupies the original path now, 403
 * outside the sandbox.
 */
export async function restoreTrashNote(
  trashPath: string,
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch("/api/vault/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: trashPath, persona }),
    })
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Restore failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Restore failed — backend unreachable (${err})` }
  }
}

/**
 * `DELETE /api/vault/trash?path=` — permanently delete one trashed note.
 * Irreversible; the caller guards it behind a confirm dialog.
 */
export async function purgeTrashNote(
  trashPath: string,
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch(
      `/api/vault/trash?path=${encodeURIComponent(trashPath)}&persona=${encodeURIComponent(persona)}`,
      { method: "DELETE" }
    )
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Delete failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Delete failed — backend unreachable (${err})` }
  }
}

/**
 * `POST /api/vault/trash/empty` — permanently delete every in-scope trashed
 * note. Irreversible; guard behind a confirm dialog.
 */
export async function emptyTrash(
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch("/api/vault/trash/empty", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona }),
    })
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Empty trash failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return {
      ok: false,
      error: `Empty trash failed — backend unreachable (${err})`,
    }
  }
}
