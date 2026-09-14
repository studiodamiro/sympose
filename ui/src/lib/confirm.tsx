import * as React from "react"

import { ConfirmDialog } from "@/components/sympose/confirm-dialog"
import { subscribeHost, getPending, clearPending } from "@/lib/confirm-store"

export function ConfirmHost() {
  const req = React.useSyncExternalStore(subscribeHost, getPending, getPending)
  return (
    <ConfirmDialog
      key={req?._id ?? "idle"}
      open={req !== null}
      onOpenChange={(open) => {
        if (!open) clearPending()
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
