/**
 * Shared drag-and-drop contract for moving a vault note by dragging its row
 * (ADR-110) — the vault tree's own folder rows and the main menu's root
 * folders both accept the same drag. A custom MIME (rather than
 * `text/plain`) keeps an OS file drag from Finder — which carries a `Files`
 * type, never this one — from matching a drop target meant for an in-app
 * note row; that OS-import path isn't wired up yet and shouldn't silently
 * half-work.
 */
const VAULT_NOTE_MIME = "application/x-sympose-vault-note-path"

export function startNoteDrag(e: React.DragEvent, path: string) {
  e.dataTransfer.setData(VAULT_NOTE_MIME, path)
  e.dataTransfer.effectAllowed = "move"
}

/** True when the event's drag payload is a vault note row, not an OS file
 *  drag or some other in-page drag. Check before `preventDefault()`ing a
 *  `dragover` so a non-note drag still gets the browser's own no-drop cue. */
export function isNoteDrag(e: React.DragEvent) {
  return e.dataTransfer.types.includes(VAULT_NOTE_MIME)
}

export function readNoteDrag(e: React.DragEvent): string | undefined {
  return e.dataTransfer.getData(VAULT_NOTE_MIME) || undefined
}
