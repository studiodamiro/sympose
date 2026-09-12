import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowDown01Icon,
  ListCollapseIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

/**
 * Broadcasts a "collapse all" pulse to every `ControlSection` beneath a
 * `ControlSectionsProvider`, however deeply nested (the Settings page nests
 * `NebulaControls`' own Toggles/Display/Forces sections inside its Knowledge
 * Nebula section). Each section keeps its own open/closed state — the pulse
 * only forces it shut once; it stays independently toggleable afterward.
 * Outside a provider (e.g. the components gallery), `collapseAll` is a no-op
 * and sections behave exactly as the plain uncontrolled `defaultOpen` before.
 */
const CollapseAllContext = React.createContext<{
  signal: number
  collapseAll: () => void
}>({ signal: 0, collapseAll: () => {} })

function ControlSectionsProvider({ children }: { children: React.ReactNode }) {
  const [signal, setSignal] = React.useState(0)
  const value = React.useMemo(
    () => ({ signal, collapseAll: () => setSignal((s) => s + 1) }),
    [signal]
  )
  return (
    <CollapseAllContext.Provider value={value}>
      {children}
    </CollapseAllContext.Provider>
  )
}

/** The button driving a `ControlSectionsProvider`'s collapse-all pulse. */
function useCollapseAll() {
  return React.useContext(CollapseAllContext).collapseAll
}

/** A ready-made trigger for `useCollapseAll` — one icon button, parked next
 *  to a page heading once there are enough `ControlSection`s below it that
 *  scanning past all of them to find one row is the actual friction. */
function CollapseAllButton({ className }: { className?: string }) {
  const collapseAll = useCollapseAll()
  return (
    <button
      type="button"
      aria-label="Collapse all sections"
      onClick={collapseAll}
      className={cn(
        "grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className
      )}
    >
      <HugeiconsIcon icon={ListCollapseIcon} className="size-4" />
    </button>
  )
}

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
  const { signal: collapseSignal } = React.useContext(CollapseAllContext)
  const [open, setOpen] = React.useState(defaultOpen)
  // Compares against the last *handled* signal, not "have I mounted before" —
  // a mount-flag flips under StrictMode's dev-only double effect invocation
  // (every section would read its own first real pulse as a second one and
  // collapse itself on load). Comparing values is idempotent no matter how
  // many times an effect for the same signal runs.
  const lastSignal = React.useRef(collapseSignal)
  React.useEffect(() => {
    if (lastSignal.current === collapseSignal) return
    lastSignal.current = collapseSignal
    setOpen(false)
  }, [collapseSignal])

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
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
      <CollapsibleContent className="h-(--collapsible-panel-height) overflow-hidden transition-[height] duration-snappy ease-snappy data-ending-style:h-0 data-starting-style:h-0">
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
      className={cn(
        // min-h-7 matches the segmented-control/toggle rows' own height (their
        // `size="sm"` button + padding + border lands here) — without it a
        // slider row, whose native range track is only `h-1.5`, collapses to
        // its label's line-height and reads as a shorter line than its
        // toggle siblings in the same list.
        "flex min-h-7 items-center justify-between gap-3",
        className
      )}
    >
      <label htmlFor={htmlFor} className="text-sm text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  )
}

export {
  ControlSection,
  ControlRow,
  ControlSectionsProvider,
  useCollapseAll,
  CollapseAllButton,
}
