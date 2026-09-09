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
  createVaultNote,
  deleteVaultNote,
  renameVaultNote,
} from "@/lib/vault-note-api"
import type { VaultNode } from "@/components/sympose/vault-tree"

/**
 * Row actions for the vault tree (ADR-084 §tree-rows). A `⋯` button — revealed
 * on row hover / focus, or by right-clicking the row (`open` is controlled by
 * the parent) — with:
 *   - **note**: Rename… (inline field overlaid on the row) and Delete… (toast
 *     confirm → moved to `.trash/`)
 *   - **folder**: New note here (creates `Folder/Untitled`, auto-numbered)
 * Owns the API calls and reports the outcome so the parent can re-pull the
 * tree and fix up the current selection.
 */
function VaultRowMenu({
  node,
  persona,
  paddingLeft,
  open,
  onOpenChange,
  onRenamed,
  onDeleted,
  onCreated,
}: {
  node: VaultNode
  persona: string
  /** Left inset of the row, so the inline rename field lines up with the label. */
  paddingLeft: number
  open: boolean
  onOpenChange: (open: boolean) => void
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
  const [busy, setBusy] = React.useState(false)

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

  const confirmDelete = () => {
    toast(`Move “${stem}” to trash?`, {
      action: {
        label: "Delete",
        onClick: async () => {
          const res = await deleteVaultNote(node.path, persona)
          if (res.ok) {
            onDeleted(node.path)
            toast.success(res.detail)
          } else {
            toast.error(res.error)
          }
        },
      },
    })
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

  if (renaming !== null) {
    return (
      <input
        autoFocus
        value={renaming}
        disabled={busy}
        aria-label={`Rename ${stem}`}
        onChange={(e) => setRenaming(e.target.value)}
        onBlur={() => setRenaming(null)}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          e.stopPropagation()
          if (e.key === "Enter") void submitRename()
          else if (e.key === "Escape") setRenaming(null)
        }}
        style={{ paddingLeft: `${paddingLeft + 20}px` }}
        className="absolute inset-y-0 left-0 right-1 my-auto h-6 rounded-md border border-border bg-background pr-2 font-mono text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
      />
    )
  }

  return (
    <DropdownMenu open={open} onOpenChange={onOpenChange}>
      <DropdownMenuTrigger
        aria-label={`${isNote ? "Note" : "Folder"} actions`}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "absolute right-1 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded text-fg-muted",
          "opacity-0 transition-opacity hover:bg-accent hover:text-foreground",
          "group-hover/row:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
        )}
      >
        <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {isNote ? (
          <>
            <DropdownMenuItem onClick={() => setRenaming(stem)}>
              <HugeiconsIcon icon={Edit01Icon} />
              Rename…
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={confirmDelete}>
              <HugeiconsIcon icon={Delete02Icon} />
              Delete…
            </DropdownMenuItem>
          </>
        ) : (
          <DropdownMenuItem onClick={newNoteHere}>
            <HugeiconsIcon icon={NoteAddIcon} />
            New note here
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { VaultRowMenu }
