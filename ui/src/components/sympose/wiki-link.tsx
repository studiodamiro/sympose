import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Atom01Icon, Note01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"

/**
 * Inline `[[Wikilink]]` (UI_DESIGN_REFERENCE.md §6.5). Rendered in the
 * `--entity` accent; hovering surfaces what a click will do — open the note in
 * the editor, or centre it in the nebula. An `unresolved` link (no target file
 * yet) is shown dimmed and dashed, matching Obsidian's ghost-link treatment.
 */
interface WikiLinkProps extends React.ComponentProps<"button"> {
  /** Wikilink target stem, e.g. `OAuth` or `Projects/Sympose/Architecture`. */
  target: string
  /** Optional display alias (`[[target|label]]`). */
  label?: string
  unresolved?: boolean
  onCenterNebula?: (target: string) => void
}

function WikiLink({
  className,
  target,
  label,
  unresolved = false,
  onClick,
  onCenterNebula,
  ...props
}: WikiLinkProps) {
  const text = label ?? target.split("/").pop() ?? target

  return (
    <HoverCard>
      <HoverCardTrigger
        render={
          <button
            type="button"
            data-slot="wiki-link"
            data-unresolved={unresolved || undefined}
            onClick={onClick}
            className={cn(
              "font-medium text-entity underline-offset-4 hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
              unresolved && "text-entity/50 decoration-dashed hover:underline",
              className
            )}
            {...props}
          />
        }
      >
        [[{text}]]
      </HoverCardTrigger>
      <HoverCardContent className="w-64 text-xs" side="top">
        <div className="flex items-center gap-1.5 font-mono text-entity">
          <HugeiconsIcon icon={Note01Icon} className="size-3.5" />
          {target}
        </div>
        <p className="mt-1.5 text-muted-foreground">
          {unresolved
            ? "Unresolved link — no note at this path yet."
            : "Opens the note in the editor."}
        </p>
        {!unresolved && (
          <button
            type="button"
            onClick={() => onCenterNebula?.(target)}
            className="mt-2 inline-flex items-center gap-1.5 text-brand hover:underline"
          >
            <HugeiconsIcon icon={Atom01Icon} className="size-3.5" />
            Centre in nebula
          </button>
        )}
      </HoverCardContent>
    </HoverCard>
  )
}

export { WikiLink }
