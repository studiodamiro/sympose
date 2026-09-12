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
   * Desktop: for the same "destination, not vault navigation" pages `plain`
   * already carves out (Settings, Agent). Stays a normal, draggable panel
   * (the resize handle is not dropped, and its ceiling lifts to the full
   * stage width instead of the ordinary half): the dragged width from before
   * `fill` turned on is remembered and restored when it turns back off, so
   * resizing a destination page never bleeds into the vault view's own
   * (cookie-persisted) width. A width dragged while filled gets its own
   * cookie (`${storageKey}.fill`) and comes back the next time `fill` turns
   * on; before that's ever happened, it starts at the same default third of
   * the stage the vault view itself defaults to — full-bleed only reads
   * right on the phone shell, where this prop plays no part at all (`phone`
   * already fills the row on its own).
   */
  fill?: boolean
  /**
   * Cookie key for the inner scroll offset. Restored on mount and written back
   * (debounced) as the user scrolls — the panel is often hidden on phone, so it
   * should come back exactly where it was left.
   */
  scrollKey?: string
  /**
   * Pinned below the scrolling surface — a sibling, not scrolled content, the
   * same way `<MarkdownPanel>`'s own "Links" row stays put under the editor.
   * Settings uses it for the Slack status / theme row so it's always in
   * reach instead of scrolling away under a tall settings list.
   */
  footer?: React.ReactNode
  /**
   * Pinned above the scrolling surface, at the panel's very top edge — a
   * non-scrolling toolbar row, styled to match stylo's own formatting
   * toolbar (`--stylo-bg` background, a `border-bottom`, `4px 6px` padding —
   * see `_toolbar_1lohh` in stylo's stylesheet) so the two panels' chrome
   * reads as one system. The vault view uses it for back/forward + new
   * note/folder (ADR-095); everything else (the section title, the tree)
   * stays regular scrolling content below it.
   */
  header?: React.ReactNode
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
  fill = false,
  scrollKey,
  footer,
  header,
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

  // An eighth of the stage, not a quarter — `<MarkdownPanel>`'s own `min`
  // mirrors this exact rule (see its comment) so neither working panel can be
  // dragged narrower than the other; keep the two in sync if this changes.
  const min = React.useCallback(
    () => Math.round(stageWidth(wrapRef.current) / 8),
    []
  )
  // Normally capped at half the stage, same as always — but while `fill` is
  // on, the ceiling lifts to the whole stage: a destination page isn't
  // competing with a neighbour for room the way the vault view is, so
  // there's no reason to stop it short of full-bleed if it's dragged there
  // on purpose (it just doesn't *start* there — see the effect below).
  const max = React.useCallback(
    () =>
      fill
        ? stageWidth(wrapRef.current)
        : Math.round(stageWidth(wrapRef.current) / 2),
    [fill]
  )
  const defaultSize = React.useCallback(
    () => Math.round(stageWidth(wrapRef.current) / 3),
    []
  )

  // A separate cookie for the `fill` (Settings / Agent) width — sharing
  // `storageKey` would mean dragging a destination page's panel silently
  // overwrites the vault view's own persisted width the moment you next
  // visit it.
  const fillStorageKey = storageKey ? `${storageKey}.fill` : undefined

  const { size, setSize, dragging, handleProps } = useResizable({
    min,
    max,
    defaultSize,
    storageKey: fill ? fillStorageKey : storageKey,
  })

  // `fill` starts the panel at its last dragged `fill` width, or the same
  // default third of the stage the vault view itself defaults to the very
  // first time — but leaves it a normal, draggable panel from there (see the
  // prop doc). Dragging while filled commits to `fillStorageKey` just like
  // any other resize, since `useResizable` above is already pointed at it.
  // Entering separately saves the vault view's own dragged width in memory to
  // restore on exit, since that isn't read back from a cookie the way the
  // two panel widths themselves are.
  const preFillSize = React.useRef<number | null>(null)
  const sizeRef = React.useRef(size)
  sizeRef.current = size
  const prevFill = React.useRef(fill)
  React.useEffect(() => {
    if (fill === prevFill.current) return
    prevFill.current = fill
    if (fill) {
      preFillSize.current = sizeRef.current
      const stored = fillStorageKey ? getCookieNumber(fillStorageKey) : null
      setSize(stored ?? defaultSize())
    } else if (preFillSize.current != null) {
      setSize(preFillSize.current)
      preFillSize.current = null
    }
  }, [fill, defaultSize, setSize, fillStorageKey])

  return (
    <div
      ref={wrapRef}
      data-slot="content-panel"
      data-state={open ? "open" : "closed"}
      data-dragging={dragging || undefined}
      className={cn(
        // z-20: the top of the stage's panel stack (menu is a separate
        // sibling), so the editor parks *behind* it and slides out from its
        // right edge. `flex flex-col` so an optional `footer` sits as a
        // `shrink-0` sibling below the scrolling surface instead of inside
        // it — same relationship `<MarkdownPanel>` keeps with its own
        // "Links" row.
        "group/panel z-20 flex min-w-0 flex-col data-dragging:select-none",
        phone
          ? // phone: one surface at a time, so the panel is an absolute layer
            // that crossfades + slides a touch from the left on reveal
            "absolute inset-0 transition-[opacity,translate] duration-300 ease-in-out"
          : // `ease-in-out`, not `ease-out` — matches `<MarkdownPanel>` and the
            // chat slot's own reveal transitions. The odd one out was most
            // noticeable on hide: the same curve run in reverse looks
            // asymmetric next to the other two panels closing alongside it.
            "relative shrink-0 py-2 pe-2 transition-[width,margin,opacity] duration-300 ease-in-out data-dragging:transition-none",
        // desktop reveal: a negative inline-start margin parks the panel one
        // width to the left (clipped by the shell row's overflow-hidden), opening
        // tweens it back to 0 so it fades and slides in from behind <MainMenu>.
        phone && !open && "-translate-x-3",
        // explicit both ways — the stage it sits in is `pointer-events-none`
        // so the ambient nebula (always the bottom of the stack) can be
        // clicked through any *other* empty stretch of it (ADR-088).
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={
        phone
          ? style
          : {
              // `size` is the single source of truth for width now — `fill`
              // only ever seeds or restores it (see the effect above), so
              // there's no separate flex/max-width clamp to keep in sync.
              width: size,
              marginInlineStart: open ? 0 : -size,
              ...style,
            }
      }
      {...props}
    >
      {header && (
        <div
          className={cn(
            "shrink-0 border-b border-border px-1.5 py-1",
            phone && plain
              ? "text-foreground"
              : "sy-frosted-panel text-panel-foreground",
            // A `header` takes over the top edge — its own corners round
            // instead, so the scroll surface below stays square there.
            phone ? !plain && "rounded-tl-lg" : "rounded-tl-lg rounded-tr-lg"
          )}
        >
          {header}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={cn(
          "flex w-full flex-1 min-h-0 flex-col gap-4 overflow-y-auto p-6",
          // plain phone pages (Settings / Agent) sit on the same background as
          // chat and the editor — no fill, no rounding
          phone && plain
            ? "text-foreground"
            : "sy-frosted-panel text-panel-foreground",
          // explicit per-corner radii — a `rounded-lg` shorthand plus a
          // `rounded-bl-none` override is unreliable (Tailwind re-emits the
          // shorthand after the longhand and re-rounds the corner).
          phone
            ? // phone: flush to every edge; only the top-left corner (where it
              // meets the icon rail) is rounded, and not for a plain page —
              // unless `header` already claimed that corner.
              !plain && !header && "rounded-tl-lg"
            : cn(
                header ? "" : "rounded-tl-lg rounded-tr-lg",
                // A `footer` takes over the bottom edge below — its own
                // corners round instead, so this surface stays square there.
                footer ? "rounded-br-none" : "rounded-br-lg",
                footer || flushBottomLeft ? "rounded-bl-none" : "rounded-bl-lg"
              ),
          contentClassName
        )}
      >
        {children}
      </div>

      {footer && (
        <div
          className={cn(
            "shrink-0 border-t border-border",
            phone && plain
              ? "text-foreground"
              : "sy-frosted-panel text-panel-foreground",
            phone
              ? "px-4 py-3"
              : cn(
                  "px-8 py-3",
                  "rounded-br-lg",
                  flushBottomLeft ? "rounded-bl-none" : "rounded-bl-lg"
                )
          )}
        >
          {footer}
        </div>
      )}

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
