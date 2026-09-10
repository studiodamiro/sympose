import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon, DeletePutBackIcon } from "@hugeicons/core-free-icons"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ConfirmDialog } from "@/components/sympose/confirm-dialog"
import {
  emptyTrash,
  fetchTrash,
  purgeTrashNote,
  restoreTrashNote,
  type TrashedNote,
} from "@/lib/vault-trash-api"

/** "3d ago" / "2h ago" / "just now" from an epoch-seconds timestamp. */
function ago(epochSeconds: number): string {
  const secs = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds))
  if (secs < 60) return "just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function splitPath(rel: string): { dir: string; name: string } {
  const i = rel.lastIndexOf("/")
  const name = (i === -1 ? rel : rel.slice(i + 1)).replace(/\.md$/i, "")
  return { dir: i === -1 ? "" : rel.slice(0, i + 1), name }
}

/**
 * The vault bin (ADR-085) — a flat list of notes `delete_note` moved to
 * `<vault>/.trash/` (the folder keeps Obsidian's name; the UI says "Bin"),
 * each restorable to its original path or deletable for good. Shown in place
 * of `<VaultTree>` when the main-menu Bin row is the active section. Owns its
 * own fetch; `refreshKey` lets the shell force a re-pull after an outside
 * change (e.g. a fresh delete from the editor).
 */
function TrashList({
  persona,
  refreshKey = 0,
  onRestored,
  className,
}: {
  persona: string
  refreshKey?: number
  /** A note was restored to `originalPath` — the shell refreshes the tree. */
  onRestored?: (originalPath: string) => void
  className?: string
}) {
  const [items, setItems] = React.useState<TrashedNote[] | null>(null)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [pendingPurge, setPendingPurge] = React.useState<TrashedNote | null>(
    null
  )
  const [pendingEmpty, setPendingEmpty] = React.useState(false)
  const [localKey, setLocalKey] = React.useState(0)

  React.useEffect(() => {
    let live = true
    fetchTrash(persona).then((rows) => {
      if (live) setItems(rows)
    })
    return () => {
      live = false
    }
  }, [persona, refreshKey, localKey])

  const reload = () => setLocalKey((k) => k + 1)

  const restore = async (row: TrashedNote) => {
    setBusy(row.trash_path)
    const res = await restoreTrashNote(row.trash_path, persona)
    setBusy(null)
    if (res.ok) {
      toast.success(res.detail)
      onRestored?.(row.original_path)
      reload()
    } else {
      toast.error(res.error)
    }
  }

  if (items === null) {
    return (
      <p className={cn("text-sm text-fg-muted", className)}>Loading bin…</p>
    )
  }

  if (items.length === 0) {
    return (
      <Empty className={cn("border-0 p-8", className)}>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <HugeiconsIcon icon={Delete02Icon} />
          </EmptyMedia>
          <EmptyTitle>Bin is empty</EmptyTitle>
          <EmptyDescription>
            Deleted notes land here and can be restored to where they were.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center justify-between pb-1">
        <span className="text-xs text-fg-muted">
          {items.length} note{items.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={() => setPendingEmpty(true)}
          className="text-xs text-fg-muted transition-colors hover:text-destructive"
        >
          Empty bin
        </button>
      </div>

      {items.map((row) => {
        const { dir, name } = splitPath(row.original_path)
        const rowBusy = busy === row.trash_path
        return (
          <div
            key={row.trash_path}
            className="group/row flex items-center gap-2 rounded-md py-1 pr-1"
          >
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate font-mono text-xs">
                {dir ? <span className="text-fg-muted">{dir}</span> : null}
                {name}
              </span>
              <span className="text-[11px] text-fg-muted">
                deleted {ago(row.deleted_at)}
              </span>
            </div>
            <button
              type="button"
              disabled={rowBusy}
              onClick={() => void restore(row)}
              aria-label={`Restore ${name}`}
              className="grid size-7 shrink-0 place-items-center rounded-md text-fg-muted opacity-0 transition-opacity group-hover/row:opacity-100 hover:bg-accent hover:text-foreground focus-visible:opacity-100 disabled:opacity-50"
            >
              <HugeiconsIcon icon={DeletePutBackIcon} className="size-4" />
            </button>
            <button
              type="button"
              disabled={rowBusy}
              onClick={() => setPendingPurge(row)}
              aria-label={`Delete ${name} permanently`}
              className="grid size-7 shrink-0 place-items-center rounded-md text-fg-muted opacity-0 transition-opacity group-hover/row:opacity-100 hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 disabled:opacity-50"
            >
              <HugeiconsIcon icon={Delete02Icon} className="size-4" />
            </button>
          </div>
        )
      })}

      <ConfirmDialog
        open={pendingPurge !== null}
        onOpenChange={(o) => !o && setPendingPurge(null)}
        title={
          pendingPurge
            ? `Delete “${splitPath(pendingPurge.original_path).name}” forever?`
            : ""
        }
        description="This removes the file from disk. It cannot be undone."
        confirmLabel="Delete forever"
        onConfirm={async () => {
          if (!pendingPurge) return
          const res = await purgeTrashNote(pendingPurge.trash_path, persona)
          if (res.ok) {
            toast.success(res.detail)
            reload()
          } else {
            toast.error(res.error)
          }
        }}
      />

      <ConfirmDialog
        open={pendingEmpty}
        onOpenChange={setPendingEmpty}
        title="Empty the bin?"
        description={`Permanently deletes ${items.length} note${
          items.length === 1 ? "" : "s"
        } from disk. This cannot be undone.`}
        confirmLabel="Empty bin"
        onConfirm={async () => {
          const res = await emptyTrash(persona)
          if (res.ok) {
            toast.success(res.detail)
            reload()
          } else {
            toast.error(res.error)
          }
        }}
      />
    </div>
  )
}

export { TrashList }
