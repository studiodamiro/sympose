import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowRight01Icon,
  Calendar03Icon,
  DashboardSquare01Icon,
  Database01Icon,
  Note01Icon,
  SearchAreaIcon,
  Settings01Icon,
  WrenchIcon,
} from "@hugeicons/core-free-icons"
import type { IconSvgElement } from "@hugeicons/react"

import { cn } from "@/lib/utils"

/**
 * Visual action-event badge — rendered inline, directly below the message that
 * produced it (UI_DESIGN_REFERENCE.md §7). Each maps to an engine action tag.
 * Clickable variants (note / daily / search / worker) get an affordance chevron
 * and behave as a button.
 */
export type ActionKind =
  | "WRITE_NOTE"
  | "APPEND_NOTE"
  | "DAILY_NOTE"
  | "SEARCH"
  | "SPAWN_WORKER"
  | "CONFIG_SET"
  | "CREATE_PERSONA"
  | "DELETE_PERSONA"

interface ActionMeta {
  icon: IconSvgElement
  label: string
  interactive: boolean
}

const ACTION_META: Record<ActionKind, ActionMeta> = {
  WRITE_NOTE: { icon: Note01Icon, label: "Note saved", interactive: true },
  APPEND_NOTE: { icon: Note01Icon, label: "Note appended", interactive: true },
  DAILY_NOTE: { icon: Calendar03Icon, label: "Reflection added", interactive: true },
  SEARCH: { icon: SearchAreaIcon, label: "Web search", interactive: true },
  SPAWN_WORKER: { icon: WrenchIcon, label: "Sub-agent", interactive: true },
  CONFIG_SET: { icon: Settings01Icon, label: "config.yaml updated", interactive: false },
  CREATE_PERSONA: { icon: Database01Icon, label: "Persona created", interactive: false },
  DELETE_PERSONA: { icon: DashboardSquare01Icon, label: "Persona archived", interactive: false },
}

interface ActionBadgeProps extends React.ComponentProps<"button"> {
  action: ActionKind
  /** Trailing detail, e.g. a note path, a query, or a config key. */
  detail?: React.ReactNode
  /** Force non-interactive rendering even for a clickable action kind. */
  static?: boolean
}

function ActionBadge({
  className,
  action,
  detail,
  static: isStatic,
  onClick,
  ...props
}: ActionBadgeProps) {
  const meta = ACTION_META[action]
  const interactive = meta.interactive && !isStatic

  const content = (
    <>
      <HugeiconsIcon icon={meta.icon} className="size-3.5 shrink-0 text-fg-muted" />
      <span className="text-fg-strong">{meta.label}</span>
      {detail != null && (
        <>
          <span className="text-fg-muted">—</span>
          <span className="truncate font-mono text-entity">{detail}</span>
        </>
      )}
      {interactive && (
        <HugeiconsIcon
          icon={ArrowRight01Icon}
          className="ml-0.5 size-3.5 shrink-0 text-fg-muted transition-transform group-hover/action:translate-x-0.5"
        />
      )}
    </>
  )

  const shared = cn(
    "group/action inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1 text-xs",
    interactive &&
      "cursor-pointer transition-colors hover:border-brand/40 hover:bg-accent focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
    className
  )

  if (!interactive) {
    return (
      <span data-slot="action-badge" data-action={action} className={shared}>
        {content}
      </span>
    )
  }

  return (
    <button
      type="button"
      data-slot="action-badge"
      data-action={action}
      className={shared}
      onClick={onClick}
      {...props}
    >
      {content}
    </button>
  )
}

export { ActionBadge, ACTION_META }
