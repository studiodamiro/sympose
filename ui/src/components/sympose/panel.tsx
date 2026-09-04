import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Matte panel shell — the primary structural container of the dashboard
 * (UI_DESIGN_REFERENCE.md §5). Solid fill + 1px border, never a shadow.
 * Compose as: Panel > PanelHeader (PanelTitle + trailing slot) > PanelContent > PanelFooter.
 */
function Panel({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      data-slot="panel"
      className={cn(
        "flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-border bg-card text-card-foreground",
        className
      )}
      {...props}
    />
  )
}

function PanelHeader({ className, ...props }: React.ComponentProps<"header">) {
  return (
    <header
      data-slot="panel-header"
      className={cn(
        "flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-3",
        className
      )}
      {...props}
    />
  )
}

function PanelTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      data-slot="panel-title"
      className={cn(
        "text-sm font-semibold tracking-wide text-brand lowercase",
        className
      )}
      {...props}
    />
  )
}

function PanelContent({
  className,
  scroll = true,
  ...props
}: React.ComponentProps<"div"> & { scroll?: boolean }) {
  return (
    <div
      data-slot="panel-content"
      className={cn(
        "min-h-0 flex-1",
        scroll && "overflow-y-auto",
        className
      )}
      {...props}
    />
  )
}

function PanelFooter({ className, ...props }: React.ComponentProps<"footer">) {
  return (
    <footer
      data-slot="panel-footer"
      className={cn(
        "flex shrink-0 items-center gap-1.5 border-t border-border px-4 py-2.5",
        className
      )}
      {...props}
    />
  )
}

export { Panel, PanelHeader, PanelTitle, PanelContent, PanelFooter }
