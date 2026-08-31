import * as React from "react"

import { cn } from "@/lib/utils"
import { getCookieNumber, setCookie } from "@/lib/cookies"
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
  /**
   * Phone shell: fill the row next to the icon rail (no dragged width, no
   * handle), sit flush to every edge, and round only the top-left corner where
   * it meets the rail.
   */
  phone?: boolean
  /**
   * Phone shell: drop the panel fill + rounding so the surface reads on the
   * same plain background as the chat and editor — used for the Settings and
   * Agent pages, which are destinations, not the vault navigation surface.
   */
  plain?: boolean
  /**
   * Cookie key for the inner scroll offset. Restored on mount and written back
   * (debounced) as the user scrolls — the panel is often hidden on phone, so it
   * should come back exactly where it was left.
   */
  scrollKey?: string
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
  phone = false,
  plain = false,
  scrollKey,
  children,
  style,
  ...props
}: ContentPanelProps) {
  const wrapRef = React.useRef<HTMLDivElement>(null)

  // Persist / restore the inner scroll offset (see `scrollKey`).
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const saveTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  )
  React.useLayoutEffect(() => {
    if (!scrollKey || !scrollRef.current) return
    const saved = getCookieNumber(scrollKey)
    if (saved != null) scrollRef.current.scrollTop = saved
  }, [scrollKey])
  React.useEffect(() => () => clearTimeout(saveTimer.current), [])
  const handleScroll = React.useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      if (!scrollKey) return
      const top = Math.round(e.currentTarget.scrollTop)
      clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(
        () => setCookie(scrollKey, String(top)),
        250
      )
    },
    [scrollKey]
  )

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
        // never grows — the content panel is navigation, it keeps its dragged
        // width and leaves the stage to the work surfaces even when it is alone.
        // z-20: the top of the stage's panel stack (menu is a separate sibling),
        // so the editor parks *behind* it and slides out from its right edge.
        "group/panel z-20 data-dragging:select-none",
        phone
          ? // phone: one surface at a time, so the panel is an absolute layer
            // that crossfades + slides a touch from the left on reveal
            "absolute inset-0 flex flex-col transition-[opacity,translate] duration-300 ease-in-out"
          : "relative shrink-0 py-2 pe-2 transition-[margin,opacity] duration-300 ease-out data-dragging:transition-none",
        // desktop reveal: a negative inline-start margin parks the panel one
        // width to the left (clipped by the shell row's overflow-hidden), opening
        // tweens it back to 0 so it fades and slides in from behind <MainMenu>.
        phone && !open && "-translate-x-3",
        open ? "opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={
        phone
          ? style
          : { width: size, marginInlineStart: open ? 0 : -size, ...style }
      }
      {...props}
    >
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={cn(
          "flex h-full w-full flex-col gap-4 overflow-y-auto p-6",
          // plain phone pages (Settings / Agent) sit on the same background as
          // chat and the editor — no fill, no rounding
          phone && plain
            ? "text-foreground"
            : "bg-panel text-panel-foreground",
          // explicit per-corner radii — a `rounded-lg` shorthand plus a
          // `rounded-bl-none` override is unreliable (Tailwind re-emits the
          // shorthand after the longhand and re-rounds the corner).
          phone
            ? // phone: flush to every edge; only the top-left corner (where it
              // meets the icon rail) is rounded, and not for a plain page
              !plain && "rounded-tl-lg"
            : cn(
                "rounded-tl-lg rounded-tr-lg rounded-br-lg",
                flushBottomLeft ? "rounded-bl-none" : "rounded-bl-lg"
              ),
          contentClassName
        )}
      >
        {children}
      </div>

      {!phone && (
        <div
          {...handleProps}
          aria-label="Resize panel"
          className="group/panel-handle absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none"
        >
          <span className="absolute inset-y-0 right-0 w-px bg-transparent transition-colors group-hover/panel-handle:bg-border group-focus-visible/panel-handle:bg-brand group-data-dragging/panel:bg-brand" />
        </div>
      )}
    </div>
  )
}

export { ContentPanel }
