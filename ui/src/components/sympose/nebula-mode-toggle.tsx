import { HugeiconsIcon } from "@hugeicons/react"
import { Orbit01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The stage's fast Explore/Focus affordance — a single icon button so flipping
 * modes doesn't require a trip through Settings → Knowledge Nebula (ADR-090).
 * Same visual idiom as `<ChatActionGroup>` (its sibling in the stage's
 * top-right corner): a `bg-secondary` chip around a `size-7` icon button,
 * `aria-pressed` carrying the active state.
 */
interface NebulaModeToggleProps extends React.ComponentProps<"div"> {
  explore?: boolean
  onToggle?: () => void
}

function NebulaModeToggle({
  className,
  explore = false,
  onToggle,
  ...props
}: NebulaModeToggleProps) {
  return (
    <div
      data-slot="nebula-mode-toggle"
      className={cn(
        "inline-flex items-center rounded-md bg-secondary p-0.5",
        className
      )}
      {...props}
    >
      <button
        type="button"
        aria-label={explore ? "Switch to Focus" : "Explore the vault graph"}
        aria-pressed={explore}
        onClick={onToggle}
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-background aria-pressed:text-foreground"
      >
        <HugeiconsIcon icon={Orbit01Icon} className="size-4" />
      </button>
    </div>
  )
}

export { NebulaModeToggle }
