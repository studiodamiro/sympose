import type { ReactNode } from "react"
import { toast } from "sonner"

import { getNotificationPreferences } from "@/lib/use-notification-preferences"
import { ConfirmLine } from "@/components/sympose/confirm-line"

export interface ConfirmRequest {
  /** The one-line question — `Move "Note" to the bin?` */
  message: string
  /** Extra line, shown in the dialog form only. */
  description?: ReactNode
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

// `confirm()` is imperative; `<ConfirmHost>` (mounted once in `App`, in
// confirm.tsx) renders whatever dialog request is pending. The pending
// request and its listeners live here rather than alongside `ConfirmHost`
// so that file exports only the component (react-refresh/only-export-components).
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

export function subscribeHost(cb: () => void): () => void {
  hostListeners.add(cb)
  return () => hostListeners.delete(cb)
}
export function getPending() {
  return pending
}
export function clearPending() {
  pending = null
  notifyHost()
}
