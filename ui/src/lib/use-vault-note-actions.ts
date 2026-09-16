import * as React from "react"

import { deleteVaultNote, renameVaultNote } from "@/lib/vault-note-api"
import { notify } from "@/lib/notify"

/**
 * The rename/delete flow shared by `<VaultRowMenu>` and `<NoteActionsMenu>`
 * (E2) — inline rename (with the Base UI focus-restoration workaround below)
 * plus move-to-trash, both against the same `renameVaultNote`/
 * `deleteVaultNote` API calls. Each caller still owns its own menu items,
 * its own rename `<input>` JSX/styling, and any node-type-specific extras
 * (folder create/delete) — this hook only owns the state and API calls
 * common to both.
 */
export function useVaultNoteActions({
  path,
  persona,
  stem,
  onRenamed,
  onDeleted,
}: {
  /** Vault-relative path of the note this menu acts on. */
  path: string
  persona: string
  /** Displayed name with `.md` already stripped — the rename field's
   *  starting value, and the confirm dialog's subject. */
  stem: string
  /** Called with the note's new vault-relative path after a rename. */
  onRenamed: (newPath: string) => void
  /** Called after the note is moved to trash. */
  onDeleted: () => void
}) {
  const [renaming, setRenaming] = React.useState<string | null>(null)
  // Rename mode is entered only once the menu that launched it has fully
  // closed — see `onMenuOpenChangeComplete`.
  const [pendingRename, setPendingRename] = React.useState(false)
  const [busy, setBusy] = React.useState(false)

  // `autoFocus` on the inline field is unreliable here: it mounts on the same
  // tick the menu closes, and Base UI's modal focus restoration (plus the
  // `inert` it briefly leaves on the rest of the page) can swallow it, so the
  // field ends up unfocused and keystrokes fall through to global shortcuts.
  // Focus it imperatively on the next frame instead, and ignore any `onBlur`
  // that fires before the field has actually held focus.
  const inputRef = React.useRef<HTMLInputElement>(null)
  const sawFocusRef = React.useRef(false)
  const renameActive = renaming !== null
  React.useEffect(() => {
    if (!renameActive) return
    sawFocusRef.current = false
    const id = requestAnimationFrame(() => {
      const el = inputRef.current
      if (el) {
        el.focus()
        el.select()
      }
    })
    return () => cancelAnimationFrame(id)
  }, [renameActive])

  // The launching menu defers entering the inline field to its own
  // `onOpenChangeComplete`: flipping `renaming` on the item click unmounts
  // the trigger mid-close, and the focus Base UI then hands back lands on
  // <body> — blurring the freshly mounted input and cancelling rename on the
  // same frame.
  const onMenuOpenChangeComplete = React.useCallback(
    (stillOpen: boolean) => {
      if (!stillOpen && pendingRename) {
        setPendingRename(false)
        setRenaming(stem)
      }
    },
    [pendingRename, stem]
  )

  const submitRename = React.useCallback(async () => {
    const name = (renaming ?? "")
      .trim()
      .replace(/\.md$/i, "")
      .replace(/^\/+|\/+$/g, "")
    if (!name || busy || name === stem) {
      setRenaming(null)
      return
    }
    setBusy(true)
    const res = await renameVaultNote(path, name, persona)
    setBusy(false)
    if (res.ok) {
      setRenaming(null)
      onRenamed(res.path)
      notify.success(res.detail)
    } else {
      notify.error(res.error)
    }
  }, [renaming, busy, stem, path, persona, onRenamed])

  const runDelete = React.useCallback(async () => {
    const res = await deleteVaultNote(path, persona)
    if (res.ok) {
      onDeleted()
      notify.success(res.detail)
    } else {
      notify.error(res.error)
    }
  }, [path, persona, onDeleted])

  const handleInputFocus = React.useCallback(() => {
    sawFocusRef.current = true
  }, [])

  const handleInputBlur = React.useCallback(() => {
    if (sawFocusRef.current) setRenaming(null)
  }, [])

  const handleInputKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") void submitRename()
      else if (e.key === "Escape") setRenaming(null)
    },
    [submitRename]
  )

  return {
    renaming,
    setRenaming,
    pendingRename,
    setPendingRename,
    busy,
    inputRef,
    onMenuOpenChangeComplete,
    submitRename,
    runDelete,
    handleInputFocus,
    handleInputBlur,
    handleInputKeyDown,
  }
}
