import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Two-or-more-way segmented control — `2D | 3D`, `Explore | Focus`
 * (UI_DESIGN_REFERENCE.md §6.4). A single-select, always-one-active row of
 * connected segments. Built on shadcn principles (cva-free here — the surface is
 * tiny — but `cn` + `data-slot` + token colors + keyboard semantics).
 */
interface SegmentedControlOption<T extends string> {
  value: T
  label: React.ReactNode
}

interface SegmentedControlProps<T extends string>
  extends Omit<React.ComponentProps<"div">, "onChange"> {
  options: SegmentedControlOption<T>[]
  value: T
  onValueChange: (value: T) => void
  size?: "sm" | "default"
  /** Options shown but not selectable (e.g. a renderer not built yet). */
  disabledValues?: T[]
  "aria-label": string
}

function SegmentedControl<T extends string>({
  className,
  options,
  value,
  onValueChange,
  size = "default",
  disabledValues,
  ...props
}: SegmentedControlProps<T>) {
  return (
    <div
      data-slot="segmented-control"
      role="radiogroup"
      className={cn(
        "inline-flex w-fit items-center rounded-md border border-border bg-card p-0.5",
        className
      )}
      {...props}
    >
      {options.map((option) => {
        const selected = option.value === value
        const disabled = disabledValues?.includes(option.value) ?? false
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-disabled={disabled || undefined}
            disabled={disabled}
            data-slot="segmented-control-item"
            data-state={selected ? "on" : "off"}
            onClick={() => !disabled && onValueChange(option.value)}
            className={cn(
              "inline-flex items-center justify-center gap-1.5 rounded-sm font-medium whitespace-nowrap transition-colors",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
              size === "sm" ? "h-6 px-2 text-xs" : "h-7 px-3 text-sm",
              disabled
                ? "cursor-not-allowed text-muted-foreground/40"
                : selected
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              "[&>svg]:size-3.5"
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export { SegmentedControl }
export type { SegmentedControlOption }
