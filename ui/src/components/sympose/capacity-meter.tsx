import * as React from "react"

import { cn } from "@/lib/utils"
import { MetaText } from "@/components/sympose/meta-text"

/**
 * Capacity meter — the Shared Memory Compactor readout
 * (UI_DESIGN_REFERENCE.md §6.4: `18/25 lines · 72%`). A 1px-framed bar carrying
 * the preset corner radius; turns amber past `warnAt` and red past `dangerAt`.
 */
interface CapacityMeterProps extends React.ComponentProps<"div"> {
  used: number
  total: number
  unit?: string
  warnAt?: number
  dangerAt?: number
}

function CapacityMeter({
  className,
  used,
  total,
  unit = "lines",
  warnAt = 0.75,
  dangerAt = 0.9,
  ...props
}: CapacityMeterProps) {
  const ratio = total > 0 ? Math.min(used / total, 1) : 0
  const pct = Math.round(ratio * 100)
  const tone =
    ratio >= dangerAt ? "danger" : ratio >= warnAt ? "warn" : "ok"

  return (
    <div
      data-slot="capacity-meter"
      data-tone={tone}
      className={cn("flex flex-col gap-1.5", className)}
      {...props}
    >
      <div
        role="meter"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={total}
        className="h-2 w-full overflow-hidden rounded-sm border border-border bg-muted"
      >
        <div
          className={cn(
            "h-full transition-[width] duration-300",
            tone === "danger" && "bg-danger",
            tone === "warn" && "bg-chip-foreground",
            tone === "ok" && "bg-ok"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <MetaText>
        {used}/{total} {unit} · {pct}%
      </MetaText>
    </div>
  )
}

export { CapacityMeter }
