import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Note01Icon, SearchAreaIcon } from "@hugeicons/core-free-icons"
import type { IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import type { ActionKind } from "@/lib/chat-mock-data"

const ACTION_META: Record<ActionKind, { icon: IconSvgElement; label: string }> = {
  WRITE_NOTE: { icon: Note01Icon, label: "Note saved" },
  APPEND_NOTE: { icon: Note01Icon, label: "Note appended" },
  SEARCH: { icon: SearchAreaIcon, label: "Searched the vault" },
}

interface ActionBadgeProps extends React.ComponentProps<"span"> {
  action: ActionKind
  /** Trailing detail, e.g. a note path or a query. */
  detail?: React.ReactNode
}

/**
 * A non-interactive chip summarizing one action a persona turn took —
 * nothing to click through to yet, so this never renders as a button.
 */
function ActionBadge({ className, action, detail, ...props }: ActionBadgeProps) {
  const meta = ACTION_META[action]

  return (
    <span
      data-slot="action-badge"
      data-action={action}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1 text-xs",
        className
      )}
      {...props}
    >
      <HugeiconsIcon icon={meta.icon} className="size-3.5 shrink-0 text-fg-muted" />
      <span className="text-fg-strong">{meta.label}</span>
      {detail != null && (
        <>
          <span className="text-fg-muted">—</span>
          <span className="truncate font-mono text-entity">{detail}</span>
        </>
      )}
    </span>
  )
}

export { ActionBadge }
