import { toast, type ExternalToast } from "sonner"

import { getNotificationPreferences } from "@/lib/use-notification-preferences"

/**
 * `sonner`'s `toast`, gated by the Notifications preference. When the user has
 * turned notifications off ("don't alert me anymore"), these feedback calls are
 * silently dropped. The delete confirmation is a separate path (`lib/confirm`)
 * and is never gated here — it needs a response.
 *
 * Swap `import { toast } from "sonner"` for `import { notify } from "@/lib/notify"`
 * at any feedback call site; the surface mirrors the parts we use.
 */
type Msg = Parameters<typeof toast.success>[0]

const on = () => getNotificationPreferences().enabled !== "off"

export const notify = {
  success: (message: Msg, data?: ExternalToast) => {
    if (on()) toast.success(message, data)
  },
  error: (message: Msg, data?: ExternalToast) => {
    if (on()) toast.error(message, data)
  },
  info: (message: Msg, data?: ExternalToast) => {
    if (on()) toast.info(message, data)
  },
  warning: (message: Msg, data?: ExternalToast) => {
    if (on()) toast.warning(message, data)
  },
  message: (message: Msg, data?: ExternalToast) => {
    if (on()) toast(message, data)
  },
}
