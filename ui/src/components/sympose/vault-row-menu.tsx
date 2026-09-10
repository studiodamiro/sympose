import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Edit01Icon,
  MoreHorizontalIcon,
  NoteAddIcon,
} from "@hugeicons/core-free-icons"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  createVaultNote,
  deleteVaultNote,
  renameVaultNote,
} from "@/lib/vault-note-api"
import { ConfirmDialog } from "@/components/sympose/confirm-dialog"
import type { VaultNode } from "@/components/sympose/vault-tree"

/**
 * The interactive line of a vault tree row plus its two ways in to the same
 * actions (ADR-084 §tree-rows):
 *
 *   - the `⋯` button, revealed on row hover / focus
 *   - a right-click (fine pointer) or ~450ms long-press (touch / pen) anywhere
 *     on the row, opening a pointer-anchored context menu
 *
 * Both carry the same rows — **note**: Rename… (an inline field overlaid on the
 * row) and Delete… (modal confirm → moved to `.trash/`, recoverable from the
 * Bin, ADR-085); **folder**: New note here (`Folder/Untitled`,
 * auto-numbered). This component owns the API calls and the rename field; the
 * row's own visual content is passed as `children`.
 */
function VaultRowMenu({
  node,
  persona,
  paddingLeft,
  className,
  children,
  onRenamed,
  onDeleted,
  onCreated,
}: {
  node: VaultNode
  persona: string
  /** Left inset of the row, so the inline rename field lines up with the label. */
  paddingLeft: number
  /** Extra classes for the row line (e.g. the `role="treeitem"` semantics). */
  className?: string
  /** The row's visual content — the disclosure / select `<button>`. */
  children: React.ReactNode
  /** A note row was renamed: its old path and the new vault-relative path. */
  onRenamed: (oldPath: string, newPath: string) => void
  /** A note row was moved to trash. */
  onDeleted: (path: string) => void
  /** A new note was created (from a folder row): its vault-relative path. */
  onCreated: (path: string) => void
}) {
  const isNote = node.type === "note"
  const stem = node.name.replace(/\.md$/i, "")
  const [renaming, setRenaming] = React.useState<string | null>(null)
  // Rename mode is entered only once the menu that launched it has fully
  // closed — see `enterRenameAfterClose`.
  const [pendingRename, setPendingRename] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [deleteOpen, setDeleteOpen] = React.useState(false)

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

  // Both menus defer entering the inline field to their `onOpenChangeComplete`:
  // flipping `renaming` on the item click unmounts the trigger mid-close, and
  // the focus Base UI then hands back lands on <body> — blurring the freshly
  // mounted input and cancelling rename on the same frame.
  const enterRenameAfterClose = (stillOpen: boolean) => {
    if (!stillOpen && pendingRename) {
      setPendingRename(false)
      setRenaming(stem)
    }
  }

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
    const res = await renameVaultNote(node.path, name, persona)
    setBusy(false)
    if (res.ok) {
      setRenaming(null)
      onRenamed(node.path, res.path)
      toast.success(res.detail)
    } else {
      toast.error(res.error)
    }
  }

  const runDelete = async () => {
    const res = await deleteVaultNote(node.path, persona)
    if (res.ok) {
      onDeleted(node.path)
      toast.success(res.detail)
    } else {
      toast.error(res.error)
    }
  }

  const newNoteHere = async () => {
    // `node.path` is the folder; try Untitled, then Untitled 2, 3, … past clashes.
    for (let n = 1; n <= 30; n++) {
      const name = n === 1 ? "Untitled" : `Untitled ${n}`
      const res = await createVaultNote(`${node.path}/${name}`, persona)
      if (res.ok) {
        onCreated(`${node.path}/${name}.md`)
        toast.success(`Created ${name}`)
        return
      }
      if (!res.error.toLowerCase().includes("already exists")) {
        toast.error(res.error)
        return
      }
    }
    toast.error("Couldn't find a free “Untitled” name")
  }

  // One row list, rendered into both the `⋯` dropdown and the context menu —
  // `ContextMenu.Item` is `Menu.Item`, so the same parts serve both.
  const items = isNote ? (
    <>
      <DropdownMenuItem onClick={() => setPendingRename(true)}>
        <HugeiconsIcon icon={Edit01Icon} />
        Rename…
      </DropdownMenuItem>
      <DropdownMenuItem
        variant="destructive"
        onClick={() => setDeleteOpen(true)}
      >
        <HugeiconsIcon icon={Delete02Icon} />
        Delete…
      </DropdownMenuItem>
    </>
  ) : (
    <DropdownMenuItem onClick={newNoteHere}>
      <HugeiconsIcon icon={NoteAddIcon} />
      New note here
    </DropdownMenuItem>
  )

  return (
    <ContextMenu onOpenChangeComplete={enterRenameAfterClose}>
      <ContextMenuTrigger
        className={cn("group/row relative flex items-center", className)}
      >
        {children}

        {renaming !== null && (
          <input
            ref={inputRef}
            value={renaming}
            disabled={busy}
            aria-label={`Rename ${stem}`}
            onChange={(e) => setRenaming(e.target.value)}
            onFocus={() => {
              sawFocusRef.current = true
            }}
            onBlur={() => {
              if (sawFocusRef.current) setRenaming(null)
            }}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation()
              if (e.key === "Enter") void submitRename()
              else if (e.key === "Escape") setRenaming(null)
            }}
            style={{ paddingLeft: `${paddingLeft + 20}px` }}
            className="absolute inset-y-0 right-1 left-0 my-auto h-6 rounded-md border border-border bg-background pr-2 font-mono text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          />
        )}

        <DropdownMenu
          modal={false}
          onOpenChangeComplete={enterRenameAfterClose}
        >
          <DropdownMenuTrigger
            aria-label={`${isNote ? "Note" : "Folder"} actions`}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              "absolute top-1/2 right-1 grid size-6 -translate-y-1/2 place-items-center rounded text-fg-muted",
              "opacity-0 transition-opacity hover:bg-accent hover:text-foreground",
              "group-hover/row:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
            )}
          >
            <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">{items}</DropdownMenuContent>
        </DropdownMenu>
      </ContextMenuTrigger>

      <ContextMenuContent>{items}</ContextMenuContent>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Move “${stem}” to the bin?`}
        description="You can restore it from the vault bin later."
        confirmLabel="Move to bin"
        onConfirm={runDelete}
      />
    </ContextMenu>
  )
}

export { VaultRowMenu }
