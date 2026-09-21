import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { ConfirmRequest } from "@/lib/confirm-store"

/** The inline toast body for `confirm()`'s `style === "inline"` path. */
export function ConfirmLine({
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
