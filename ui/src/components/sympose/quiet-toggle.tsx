import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Small, quiet panel-corner control (UI_DESIGN_REFERENCE.md §5) — the optional
 * light/dark and 2D|3D quick-toggles that may dock to a panel foot. Deliberately
 * understated: muted text, hairline border, no fill until hover.
 */
interface QuietToggleProps extends React.ComponentProps<"button"> {
  active?: boolean
}

function QuietToggle({
  className,
  active = false,
  type = "button",
  ...props
}: QuietToggleProps) {
  return (
    <button
      type={type}
      data-slot="quiet-toggle"
      data-active={active || undefined}
      className={cn(
        "inline-flex h-6 items-center gap-1 rounded-md border border-border bg-transparent px-2 font-mono text-[11px] text-fg-muted transition-colors",
        "hover:bg-accent hover:text-foreground",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-40",
        "data-active:border-brand/50 data-active:text-brand",
        "[&>svg]:size-3",
        className
      )}
      {...props}
    />
  )
}

export { QuietToggle }
