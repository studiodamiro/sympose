import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

/**
 * A collapsible group in the nebula control stack — `Filters`, `Groups`,
 * `Display`, `Forces` (UI_DESIGN_REFERENCE.md §6.3). Header row with a rule line
 * beneath it, matching Obsidian's graph-view control sections.
 */
interface ControlSectionProps {
  title: string
  defaultOpen?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
  className?: string
}

function ControlSection({
  title,
  defaultOpen = false,
  icon,
  children,
  className,
}: ControlSectionProps) {
  return (
    <Collapsible
      defaultOpen={defaultOpen}
      data-slot="control-section"
      className={cn("border-b border-border/60 last:border-b-0", className)}
    >
      <CollapsibleTrigger
        className={cn(
          "group/control flex w-full items-center justify-between gap-2 py-2.5 text-left text-sm font-medium",
          "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        )}
      >
        <span className="flex items-center gap-2 [&>svg]:size-3.5 [&>svg]:text-fg-muted">
          {icon}
          {title}
        </span>
        <HugeiconsIcon
          icon={ArrowDown01Icon}
          className="size-4 text-fg-muted transition-transform group-data-panel-open/control:rotate-180"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="h-(--collapsible-panel-height) overflow-hidden transition-[height] duration-150 ease-out data-ending-style:h-0 data-starting-style:h-0">
        <div className="flex flex-col gap-3 pt-1 pb-3">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}

/** A single labelled control row inside a ControlSection. */
function ControlRow({
  label,
  htmlFor,
  children,
  className,
}: {
  label: React.ReactNode
  htmlFor?: string
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      data-slot="control-row"
      className={cn("flex items-center justify-between gap-3", className)}
    >
      <label htmlFor={htmlFor} className="text-sm text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  )
}

export { ControlSection, ControlRow }
