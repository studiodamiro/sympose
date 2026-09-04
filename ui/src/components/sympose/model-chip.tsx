import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { CloudIcon, ComputerIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getPersona } from "@/lib/personas"

/**
 * Muted backend-model chip shown next to a persona handle
 * (UI_DESIGN_REFERENCE.md §7 / §8). Local models get an "on-device / private"
 * indicator; cloud models a subtle cloud glyph. Never loud — it is metadata.
 */
interface ModelChipProps extends React.ComponentProps<"span"> {
  /** Model family string, e.g. `gemini-3.6-flash` or `ollama:qwen2.5-14b`. */
  model?: string
  /** Resolve model + tier from a persona handle instead. */
  handle?: string
  tier?: "cloud" | "local"
}

function ModelChip({
  className,
  model,
  handle,
  tier,
  ...props
}: ModelChipProps) {
  const persona = handle ? getPersona(handle) : undefined
  const resolvedModel = model ?? persona?.model ?? "unknown"
  const resolvedTier =
    tier ?? persona?.tier ?? (resolvedModel.includes(":") ? "local" : "cloud")
  const isLocal = resolvedTier === "local"

  return (
    <span
      data-slot="model-chip"
      data-tier={resolvedTier}
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center gap-1 rounded-md bg-chip px-1.5 font-mono text-[11px] whitespace-nowrap [&>svg]:size-3",
        isLocal ? "text-ok" : "text-fg-muted",
        className
      )}
      title={isLocal ? "On-device — private, air-gapped" : "Cloud model"}
      {...props}
    >
      <HugeiconsIcon icon={isLocal ? ComputerIcon : CloudIcon} />
      {resolvedModel}
    </span>
  )
}

export { ModelChip }
