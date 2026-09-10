import * as React from "react"
import { toast } from "sonner"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getNotificationPreferences } from "@/lib/use-notification-preferences"
import { ConfirmDialog } from "@/components/sympose/confirm-dialog"

export interface ConfirmRequest {
  /** The one-line question — `Move "Note" to the bin?` */
  message: string
  /** Extra line, shown in the dialog form only. */
  description?: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: "destructive" | "default"
  /**
   * Irreversible (permanent delete / empty bin). Always asks — through the
   * dialog, a hard stop — regardless of the "Delete confirmation" preference.
   */
  permanent?: boolean
  onConfirm: () => void | Promise<void>
}

// `confirm()` is imperative; `<ConfirmHost>` (mounted once in `App`) renders
// whatever dialog request is pending.
let pending: (ConfirmRequest & { _id: number }) | null = null
let seq = 0
const hostListeners = new Set<() => void>()

function notifyHost() {
  for (const l of hostListeners) l()
}

/**
 * Ask before a destructive action, honouring the user's "Delete confirmation"
 * preference: `dialog` → the centred modal; `inline` → a one-line, colour-coded
 * toast at the notifications position; `none` → run it straight away (the file
 * still goes to the Bin, so it stays recoverable). `permanent` requests ignore
 * `none` / `inline` and always use the modal.
 */
export function confirm(req: ConfirmRequest): void {
  const style = getNotificationPreferences().confirm

  if (!req.permanent && style === "none") {
    void req.onConfirm()
    return
  }
  if (req.permanent || style === "dialog") {
    pending = { ...req, _id: ++seq }
    notifyHost()
    return
  }
  // inline: a persistent, action-bearing toast at the configured corner
  const tone = req.tone ?? "destructive"
  toast.custom(
    (id) => (
      <ConfirmLine req={req} tone={tone} onDone={() => toast.dismiss(id)} />
    ),
    { duration: Infinity, position: getNotificationPreferences().position }
  )
}

function ConfirmLine({
  req,
  tone,
  onDone,
}: {
  req: ConfirmRequest
  tone: "destructive" | "default"
  onDone: () => void
}) {
  const [busy, setBusy] = React.useState(false)
  const run = async () => {
    if (busy) return
    setBusy(true)
    try {
      await req.onConfirm()
    } finally {
      onDone()
    }
  }
  return (
    <div
      className={cn(
        "flex w-[min(22rem,calc(100vw-2rem))] items-center gap-2.5 rounded-lg border px-3 py-2 text-sm shadow-2xl ring-1 ring-foreground/5",
        "bg-panel/95 backdrop-blur-xl",
        tone === "destructive" ? "border-destructive/30" : "border-border"
      )}
    >
      <HugeiconsIcon
        icon={Alert02Icon}
        strokeWidth={2}
        className={cn(
          "size-4 shrink-0",
          tone === "destructive" ? "text-destructive" : "text-muted-foreground"
        )}
      />
      <span className="min-w-0 flex-1 truncate text-foreground">
        {req.message}
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={onDone}
        className="shrink-0 rounded px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
      >
        {req.cancelLabel ?? "Cancel"}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={run}
        className={cn(
          "shrink-0 rounded px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50",
          tone === "destructive"
            ? "bg-destructive/15 text-destructive hover:bg-destructive/25"
            : "bg-primary/15 text-primary hover:bg-primary/25"
        )}
      >
        {req.confirmLabel ?? "Confirm"}
      </button>
    </div>
  )
}

function subscribeHost(cb: () => void): () => void {
  hostListeners.add(cb)
  return () => hostListeners.delete(cb)
}
function getPending() {
  return pending
}

export function ConfirmHost() {
  const req = React.useSyncExternalStore(subscribeHost, getPending, getPending)
  const clear = () => {
    pending = null
    notifyHost()
  }
  return (
    <ConfirmDialog
      key={req?._id ?? "idle"}
      open={req !== null}
      onOpenChange={(open) => {
        if (!open) clear()
      }}
      title={req?.message ?? ""}
      description={req?.description}
      confirmLabel={req?.confirmLabel}
      cancelLabel={req?.cancelLabel}
      destructive={(req?.tone ?? "destructive") === "destructive"}
      onConfirm={() => req?.onConfirm()}
    />
  )
}
