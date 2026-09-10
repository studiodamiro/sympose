import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

/**
 * A controlled yes/no confirm modal for irreversible-ish actions — moving a
 * note to the bin, deleting it for good, emptying the bin. This is the
 * `dialog` form of `confirm()` (`lib/confirm`) and the only form the permanent
 * actions ever use; `<ConfirmHost>` owns `open` and feeds it the pending
 * request (ADR-087).
 *
 * `onConfirm` may be async — the dialog stays open with the confirm button
 * disabled until it settles, then closes itself.
 */
function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = true,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** Style the confirm button as destructive (default true). */
  destructive?: boolean
  onConfirm: () => void | Promise<void>
}) {
  const [busy, setBusy] = React.useState(false)

  const run = async () => {
    if (busy) return
    setBusy(true)
    try {
      await onConfirm()
      onOpenChange(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : null}
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" disabled={busy} />}>
            {cancelLabel}
          </DialogClose>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={busy}
            onClick={run}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export { ConfirmDialog }
