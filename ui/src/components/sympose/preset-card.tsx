import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { CheckmarkCircle02Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * Selectable theme-preset card for Settings → Appearance
 * (UI_DESIGN_REFERENCE.md §3.1 / §6.4). Shows the preset name, its mode, and a
 * strip of swatches (background, accent, node fills). Flat — selection is a 1px
 * accent border + a check, not elevation.
 */
export interface ThemePreset {
  name: string
  mode: string
  /** CSS colors: [background, foreground/ink, accent, ...node fills]. */
  swatches: string[]
}

interface PresetCardProps
  extends Omit<React.ComponentProps<"button">, "onSelect"> {
  preset: ThemePreset
  selected?: boolean
}

function PresetCard({
  className,
  preset,
  selected = false,
  ...props
}: PresetCardProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      data-slot="preset-card"
      data-selected={selected || undefined}
      className={cn(
        "group/preset relative flex flex-col gap-2.5 rounded-lg border p-3 text-left transition-colors",
        "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
        selected
          ? "border-brand bg-accent"
          : "border-border hover:border-brand/40 hover:bg-accent/50",
        className
      )}
      {...props}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-fg-strong">{preset.name}</span>
        {selected && (
          <HugeiconsIcon
            icon={CheckmarkCircle02Icon}
            className="size-4 text-brand"
          />
        )}
      </div>
      <div className="flex h-8 overflow-hidden rounded-md border border-border">
        {preset.swatches.map((color, i) => (
          <span
            key={i}
            className="flex-1"
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
      <span className="font-mono text-[11px] text-fg-muted">{preset.mode}</span>
    </button>
  )
}

export { PresetCard }
