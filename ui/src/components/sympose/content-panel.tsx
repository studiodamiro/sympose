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
  /**
   * Revealed when true (default), collapsed when false. The panel stays mounted
   * either way and transitions its inline-start margin / opacity, so it fades
   * and slides in from behind `<MainMenu>` on reveal and back out on hide. The
   * ancestor that clips it while parked must be `overflow-hidden`.
   */
  open?: boolean
  /**
   * Square off the bottom-left corner so the *last* menu row (the account row),
   * when it is the active row, fuses flush into the panel instead of leaving a
   * sliver of background inside the rounded corner.
   */
  flushBottomLeft?: boolean
}

function stageWidth(el: HTMLElement | null): number {
  return el?.parentElement?.getBoundingClientRect().width ?? window.innerWidth
}

function ContentPanel({
  className,
  contentClassName,
  storageKey,
  open = true,
  flushBottomLeft = false,
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
      data-state={open ? "open" : "closed"}
      data-dragging={dragging || undefined}
      className={cn(
        "group/panel relative shrink-0 py-2 pe-2 data-dragging:select-none",
        // reveal: a negative inline-start margin parks the panel one width to the
        // left (clipped by the shell row's overflow-hidden); opening tweens it
        // back to 0 so it fades and slides in from behind <MainMenu>, and
        // reverses on hide. Width itself never animates. Suppressed mid-drag.
        "transition-[margin,opacity] duration-300 ease-out data-dragging:transition-none",
        open ? "opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={{
        width: size,
        marginInlineStart: open ? 0 : -size,
        ...style,
      }}
      {...props}
    >
      <div
        className={cn(
          // explicit per-corner radii — a `rounded-lg` shorthand plus a
          // `rounded-bl-none` override is unreliable (Tailwind re-emits the
          // shorthand after the longhand and re-rounds the corner).
          "flex h-full w-full flex-col gap-4 overflow-y-auto rounded-tl-lg rounded-tr-lg rounded-br-lg bg-panel p-6 text-panel-foreground",
          flushBottomLeft ? "rounded-bl-none" : "rounded-bl-lg",
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
