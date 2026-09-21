import { vaultScopedKey } from "@/lib/cookies"

/**
 * Local-only safety net for an unsaved note edit that's about to close
 * because the active vault is switching, not because the user picked
 * another note — see `markdown-panel.tsx`'s leave-note flush. A normal
 * note-to-note switch (or leaving `/shell` entirely) still flushes straight
 * to the vault via `PUT /api/vault/note`; only a vault switch routes
 * through here instead, since by the time that request would land the
 * backend's active vault has already changed, and the same relative path
 * could now name a completely different file.
 *
 * `localStorage`, not a cookie (see `lib/cookies.ts`'s own convention) —
 * this holds a whole note body, not a small UI-preference value.
 */

const PREFIX = "sympose:draft"

function draftKey(vaultPath: string | null, notePath: string): string {
  return `${vaultScopedKey(PREFIX, vaultPath)}:${notePath}`
}

/** Stash `text` for `notePath` as it stood in `vaultPath` when its note
 *  panel closed mid-edit. Best-effort — silently no-ops if `localStorage`
 *  is unavailable (private browsing, quota exceeded), since this is a
 *  safety net, not a guarantee. */
export function stashDraft(
  vaultPath: string | null,
  notePath: string,
  text: string
): void {
  try {
    window.localStorage.setItem(
      draftKey(vaultPath, notePath),
      JSON.stringify({ text, savedAt: Date.now() })
    )
  } catch {
    // best-effort
  }
}
