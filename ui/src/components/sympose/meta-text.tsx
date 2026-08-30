import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Muted monospace metadata — timestamps, token counts, `ms` readouts, YAML keys.
 * Maps to the `--fg-muted` semantic token (UI_DESIGN_REFERENCE.md §3.2).
 */
function MetaText({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="meta-text"
      className={cn(
        "font-mono text-xs text-fg-muted tabular-nums",
        className
      )}
      {...props}
    />
  )
}

/**
 * Time-to-first-token / latency chip, e.g. `0.68 TTFT` or `<2ms`.
 * Rendered as calm muted text, never a loud badge.
 */
function LatencyReadout({
  className,
  value,
  label = "TTFT",
  ...props
}: React.ComponentProps<"span"> & { value: string | number; label?: string }) {
  return (
    <MetaText
      data-slot="latency-readout"
      className={cn("inline-flex items-center gap-1", className)}
      {...props}
    >
      <span className="text-fg-strong">{value}</span>
      <span>{label}</span>
    </MetaText>
  )
}

export { MetaText, LatencyReadout }
