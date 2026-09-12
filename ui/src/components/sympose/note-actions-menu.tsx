import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Edit01Icon,
  MoreHorizontalIcon,
  PinIcon,
  PinOffIcon,
} from "@hugeicons/core-free-icons"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { confirm } from "@/lib/confirm"
import { notify } from "@/lib/notify"
import { deleteVaultNote, renameVaultNote } from "@/lib/vault-note-api"

/**
 * The `⋯` menu on the editor toolbar — Pin/Unpin (local-only prep, same as
 * the vault-tree row menu), Rename / Delete for the open note (ADR-084).
 * Rename swaps the button for an inline field (Enter commits, Esc /
 * blur cancels); Delete asks first via `confirm()` (dialog / inline / none, per
 * the Notifications preference — ADR-087). Owns
 * the API calls itself; the parent is only told the note moved so it can
 * repoint `selectedNote` and refresh the tree.
 */
function NoteActionsMenu({
  path,
  persona,
  onRenamed,
  onDeleted,
  pinned = false,
  onTogglePin,
}: {
  /** Vault-relative path of the open note. */
  path: string
  persona: string
  /** Called with the note's new vault-relative path after a rename. */
  onRenamed: (newPath: string) => void
  /** Called after the note is moved to trash. */
  onDeleted: () => void
  /** Is the open note currently pinned. */
  pinned?: boolean
  /** Toggle the open note's pinned state. Omit to hide the row. */
  onTogglePin?: (path: string) => void
}) {
  const stem = React.useMemo(() => {
    const base = path.split("/").pop() ?? path
    return base.replace(/\.md$/i, "")
  }, [path])

  const [renaming, setRenaming] = React.useState<string | null>(null)
  // Rename mode is entered only once the menu has fully closed — see the
  // `onOpenChangeComplete` handler below.
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

  const submitRename = async () => {
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
  }

  const runDelete = async () => {
    const res = await deleteVaultNote(path, persona)
    if (res.ok) {
      onDeleted()
      notify.success(res.detail)
    } else {
      notify.error(res.error)
    }
  }

  if (renaming !== null) {
    return (
      <input
        ref={inputRef}
        value={renaming}
        disabled={busy}
        aria-label="New note name"
        onChange={(e) => setRenaming(e.target.value)}
        onFocus={() => {
          sawFocusRef.current = true
        }}
        onBlur={() => {
          if (sawFocusRef.current) setRenaming(null)
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") void submitRename()
          else if (e.key === "Escape") setRenaming(null)
        }}
        className="h-7 w-44 rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
      />
    )
  }

  return (
    <>
      <DropdownMenu
        modal={false}
        onOpenChangeComplete={(open) => {
          // Swap the trigger for the inline field only after Base UI has
          // finished closing the menu and returning focus to the trigger.
          // Doing it on the item click instead unmounts the trigger mid-close,
          // and the focus Base UI then hands back lands on <body> — blurring
          // the freshly mounted input and cancelling rename on the same frame.
          if (!open && pendingRename) {
            setPendingRename(false)
            setRenaming(stem)
          }
        }}
      >
        <DropdownMenuTrigger
          aria-label="Note actions"
          className="grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-[popup-open]:bg-accent data-[popup-open]:text-foreground"
        >
          <HugeiconsIcon icon={MoreHorizontalIcon} className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
          {onTogglePin && (
            <DropdownMenuItem onClick={() => onTogglePin(path)}>
              <HugeiconsIcon icon={pinned ? PinOffIcon : PinIcon} />
              {pinned ? "Unpin note" : "Pin note"}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onClick={() => setPendingRename(true)}>
            <HugeiconsIcon icon={Edit01Icon} />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() =>
              confirm({
                message: `Move “${stem}” to the bin?`,
                description: "You can restore it from the vault bin later.",
                confirmLabel: "Move to bin",
                onConfirm: runDelete,
              })
            }
          >
            <HugeiconsIcon icon={Delete02Icon} />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}

export { NoteActionsMenu }
