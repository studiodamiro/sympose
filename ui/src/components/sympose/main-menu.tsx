import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import { Settings01Icon, SidebarLeft01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { useResizable } from "@/lib/use-resizable"
import { Logo } from "@/components/logo"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

/**
 * Sympose main menu — the primary app-shell navigation (see the design
 * screenshots). No shadcn primitive covers exactly this, so it is hand-built on
 * the same principles: `cn` + `data-slot` hooks + semantic tokens + preset
 * radius. Items are the top-level Obsidian vault folders.
 *
 * Layout invariants the design is strict about:
 *
 * 1. Icon axis. Header, list and footer share a `--menu-pad` inline-start
 *    padding and every glyph sits centred in a `--menu-slot` box. At the
 *    minimum width (`MENU_MIN` = `--menu-slot` + 2·`--menu-pad`) that slot is
 *    exactly centred, so the icon centreline never moves as the menu resizes —
 *    only the label track opens and closes.
 * 2. Active vs hover. Rows have no inline-end padding, so a row fills to the
 *    menu's right edge on its own. A hovered row adds a `--menu-pad` end margin
 *    to pull clear as a detached pill; the *active* row keeps no end margin and
 *    only its left corners rounded, carrying the panel fill (`bg-panel`) so it
 *    butts straight against the panel the page renders flush beside it — no seam.
 * 3. Resize. The right edge is a drag handle. Width is free between `MENU_MIN`
 *    (the collapsed rail) and `MENU_MAX`; releasing below `COLLAPSE_AT` snaps to
 *    the rail. `collapsed` is derived from the width; the `collapsed` prop and
 *    the logo / footer toggles set it imperatively.
 */

/** Keep in sync with `--menu-slot` (2rem) + 2·`--menu-pad` (0.5rem) below. */
const MENU_MIN = 48
/** The previous fixed expanded width (`16rem`) — now the drag ceiling. */
const MENU_MAX = 256
/** Release the handle narrower than this and the menu snaps to the rail. */
const COLLAPSE_AT = 140

export interface MainMenuItem {
  /** Stable id — also the vault folder name / route segment. */
  id: string
  label: string
  icon: IconSvgElement
}

/**
 * Sentinel `activeId` / select-callback ids for the footer rows (Settings and
 * the account), which live outside `items` but share the same active-row and
 * toggle behaviour.
 */
export const MENU_SETTINGS_ID = "__settings__"
export const MENU_ACCOUNT_ID = "__account__"

interface MainMenuProps extends Omit<React.ComponentProps<"nav">, "onSelect"> {
  items: MainMenuItem[]
  activeId?: string
  onSelectItem?: (item: MainMenuItem) => void
  /** Controlled collapsed state. Omit for uncontrolled. */
  collapsed?: boolean
  defaultCollapsed?: boolean
  onCollapsedChange?: (collapsed: boolean) => void
  /** Settings row clicked. Pair with `activeId === MENU_SETTINGS_ID`. */
  onOpenSettings?: () => void
  /** Account row clicked. Pair with `activeId === MENU_ACCOUNT_ID`. */
  onSelectAccount?: () => void
  /** Account row label + avatar seed. */
  account?: { name: string }
  /** Cookie key to persist the dragged width as a user preference. */
  storageKey?: string
}

/**
 * Row shell — `w-full` reaches the menu's right edge (the list has no inline-end
 * padding). `<button>` shrink-wraps otherwise, so the width is explicit. No
 * radius of its own (the variant sets it): keeping `rounded-md` here and trying
 * to override it with `rounded-r-none` is unreliable — Tailwind emits the
 * shorthand after the longhand and re-rounds the corner.
 */
const ROW =
  "flex h-9 w-full shrink-0 items-center gap-2 text-sm transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"

/**
 * Hover / idle row — a detached pill, held `--menu-pad` clear of the menu's
 * right edge so it never touches the panel.
 */
const ROW_MUTED =
  "w-[calc(100%-var(--menu-pad))] rounded-md text-muted-foreground hover:bg-accent/50 hover:text-foreground"

/**
 * Active row — the panel fill, left corners only, full width: it runs all the
 * way to the menu's right edge and butts flush against the panel.
 */
const ROW_ACTIVE = "rounded-l-md bg-panel font-medium text-panel-foreground"

/** Fixed icon slot — the alignment axis, identical at every width. */
const SLOT = "grid w-(--menu-slot) shrink-0 place-items-center"

/**
 * Label track. Stays `flex-1` at every width — at `MENU_MIN` the flex math
 * leaves it exactly 0-wide, so it needs no width/flex change of its own (those
 * snap instantly and jitter). Its width is carried entirely by the `<nav>`
 * width; only opacity is animated here, for a clean fade.
 */
const LABEL =
  "min-w-0 flex-1 truncate pr-2 text-left opacity-100 transition-opacity duration-200 ease-out group-data-collapsed/menu:opacity-0"

function MainMenu({
  className,
  items,
  activeId,
  onSelectItem,
  collapsed: collapsedProp,
  defaultCollapsed = false,
  onCollapsedChange,
  onOpenSettings,
  onSelectAccount,
  account = { name: "Agent" },
  storageKey,
  style,
  ...props
}: MainMenuProps) {
  const lastExpanded = React.useRef(MENU_MAX)

  const {
    size: width,
    commit,
    dragging,
    handleProps,
  } = useResizable({
    min: MENU_MIN,
    max: MENU_MAX,
    defaultSize: (collapsedProp ?? defaultCollapsed) ? MENU_MIN : MENU_MAX,
    storageKey,
    onCommit: (s) => (s < COLLAPSE_AT ? MENU_MIN : s),
  })

  const collapsed = width < COLLAPSE_AT

  // Remember the last genuinely-expanded width so a toggle restores to it.
  React.useEffect(() => {
    if (width >= COLLAPSE_AT) lastExpanded.current = width
  }, [width])

  // Notify the parent whenever the derived collapsed state flips.
  const prevCollapsed = React.useRef(collapsed)
  React.useEffect(() => {
    if (collapsed === prevCollapsed.current) return
    prevCollapsed.current = collapsed
    onCollapsedChange?.(collapsed)
  }, [collapsed, onCollapsedChange])

  const setCollapsed = React.useCallback(
    (next: boolean) => commit(next ? MENU_MIN : lastExpanded.current),
    [commit]
  )

  // React to the controlled `collapsed` prop *changing* (not every render, so a
  // parent that never listens to onCollapsedChange doesn't fight the drag).
  const prevProp = React.useRef(collapsedProp)
  React.useEffect(() => {
    if (collapsedProp === undefined || collapsedProp === prevProp.current)
      return
    prevProp.current = collapsedProp
    commit(collapsedProp ? MENU_MIN : lastExpanded.current)
  }, [collapsedProp, commit])

  return (
    <nav
      data-slot="main-menu"
      data-collapsed={collapsed || undefined}
      data-dragging={dragging || undefined}
      aria-label="Main menu"
      className={cn(
        "group/menu relative flex h-full flex-col overflow-x-hidden bg-background text-foreground",
        "transition-[width] duration-200 ease-out data-dragging:transition-none data-dragging:select-none",
        "*:ps-(--menu-pad)",
        className
      )}
      style={
        {
          width,
          "--menu-pad": "0.5rem",
          "--menu-slot": "2rem",
          ...style,
        } as React.CSSProperties
      }
      {...props}
    >
      {/* header — logo doubles as the expand/collapse toggle */}
      <div className="flex h-14 shrink-0 items-center gap-2">
        <div className={SLOT}>
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand menu" : "Collapse menu"}
            aria-expanded={!collapsed}
            className="grid size-8 place-items-center rounded-md transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <Logo className="size-6" />
          </button>
        </div>
        <span className={cn(LABEL, "text-base font-semibold tracking-tight")}>
          Sympose
        </span>
      </div>

      {/* folders */}
      <ul className="flex min-h-0 flex-1 flex-col gap-1 overflow-x-hidden overflow-y-auto py-2">
        {items.map((item) => {
          const active = item.id === activeId
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelectItem?.(item)}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                className={cn(ROW, active ? ROW_ACTIVE : ROW_MUTED)}
              >
                <span className={SLOT}>
                  <HugeiconsIcon icon={item.icon} className="size-4.5" />
                </span>
                <span className={LABEL}>{item.label}</span>
              </button>
            </li>
          )
        })}
      </ul>

      {/* footer — collapse · settings · account */}
      <div className="shrink-0 py-2">
        {/* divider spans exactly the hover-pill footprint (ROW_MUTED width) */}
        <div className="mb-2 w-[calc(100%-var(--menu-pad))] border-t border-border" />
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className={cn(ROW, ROW_MUTED)}
          >
            <span className={SLOT}>
              <HugeiconsIcon
                icon={SidebarLeft01Icon}
                className={cn(
                  "size-4.5 transition-transform",
                  collapsed && "rotate-180"
                )}
              />
            </span>
            <span className={LABEL}>Collapse</span>
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            aria-current={activeId === MENU_SETTINGS_ID ? "page" : undefined}
            className={cn(
              ROW,
              activeId === MENU_SETTINGS_ID ? ROW_ACTIVE : ROW_MUTED
            )}
          >
            <span className={SLOT}>
              <HugeiconsIcon icon={Settings01Icon} className="size-4.5" />
            </span>
            <span className={LABEL}>Settings</span>
          </button>
          <button
            type="button"
            onClick={onSelectAccount}
            aria-current={activeId === MENU_ACCOUNT_ID ? "page" : undefined}
            className={cn(
              ROW,
              activeId === MENU_ACCOUNT_ID ? ROW_ACTIVE : ROW_MUTED
            )}
          >
            <span className={SLOT}>
              <Avatar size="sm">
                <AvatarFallback className="bg-accent text-[11px] font-medium uppercase">
                  {account.name.slice(0, 1)}
                </AvatarFallback>
              </Avatar>
            </span>
            <span className={LABEL}>{account.name}</span>
          </button>
        </div>
      </div>

      {/* right-edge resize handle */}
      <div
        {...handleProps}
        aria-label="Resize menu"
        className="group/handle absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none ps-0!"
      >
        <span className="absolute inset-y-0 right-0 w-px bg-transparent transition-colors group-hover/handle:bg-border group-focus-visible/handle:bg-brand group-data-dragging/menu:bg-brand" />
      </div>
    </nav>
  )
}

export { MainMenu }
