import * as React from "react"

import { cn } from "@/lib/utils"
import { useResizable } from "@/lib/use-resizable"

/**
 * The content panel that docks flush against `<MainMenu>` (see the design
 * screenshots). Borderless `bg-panel`, fully rounded, symmetric top/bottom
 * margin, right margin — its straight left edge sits against the menu so the
 * active row fuses into it.
 *
 * Its right edge is a drag handle. Width is free between a quarter and a half of
 * the "stage" (the parent flex container — the viewport on a full page, the
 * frame in a boxed demo); bounds re-clamp on window resize. `storageKey`
 * persists the width as a user preference (cookie).
 */
interface ContentPanelProps extends React.ComponentProps<"div"> {
  storageKey?: string
  /** Extra classes on the inner scrolling surface. */
  contentClassName?: string
}

function stageWidth(el: HTMLElement | null): number {
  return el?.parentElement?.getBoundingClientRect().width ?? window.innerWidth
}

function ContentPanel({
  className,
  contentClassName,
  storageKey,
  children,
  style,
  ...props
}: ContentPanelProps) {
  const wrapRef = React.useRef<HTMLDivElement>(null)

  const min = React.useCallback(
    () => Math.round(stageWidth(wrapRef.current) / 4),
    []
  )
  const max = React.useCallback(
    () => Math.round(stageWidth(wrapRef.current) / 2),
    []
  )
  const defaultSize = React.useCallback(
    () => Math.round(stageWidth(wrapRef.current) / 3),
    []
  )

  const { size, dragging, handleProps } = useResizable({
    min,
    max,
    defaultSize,
    storageKey,
  })

  return (
    <div
      ref={wrapRef}
      data-slot="content-panel"
      data-dragging={dragging || undefined}
      className={cn(
        "group/panel relative shrink-0 py-2 pe-2 data-dragging:select-none",
        className
      )}
      style={{ width: size, ...style }}
      {...props}
    >
      <div
        className={cn(
          "flex h-full w-full flex-col gap-4 overflow-y-auto rounded-lg bg-panel p-6 text-panel-foreground",
          contentClassName
        )}
      >
        {children}
      </div>

      <div
        {...handleProps}
        aria-label="Resize panel"
        className="group/panel-handle absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none"
      >
        <span className="absolute inset-y-0 right-0 w-px bg-transparent transition-colors group-hover/panel-handle:bg-border group-focus-visible/panel-handle:bg-brand group-data-dragging/panel:bg-brand" />
      </div>
    </div>
  )
}

export { ContentPanel }
