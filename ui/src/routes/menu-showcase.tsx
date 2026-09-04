import * as React from "react"

import { cn } from "@/lib/utils"
import { VAULT_FOLDERS } from "@/lib/vault-folders"
import { ContentPanel, MainMenu, type MainMenuItem } from "@/components/sympose"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const ITEMS: MainMenuItem[] = VAULT_FOLDERS.map((f) => ({
  id: f.name,
  label: f.name,
  icon: f.icon,
}))

const PLACEHOLDER =
  "This is a placeholder. But I must explain to you how all this mistaken idea of denouncing pleasure and praising pain was born and I will give you a complete account of the system, and expound the actual teachings of the great explorer of the truth, the master-builder of human happiness. No one rejects, dislikes, or avoids pleasure itself, because it is pleasure, but because"

/**
 * Menu + content panel. The menu is `bg-background`, no border. The panel is a
 * borderless `bg-panel` card, `rounded-lg`, with a symmetric top/bottom margin
 * and a right margin, docked flush to the menu on the left. Its rounded left
 * corners round away at the very top and bottom; along the straight stretch
 * between them the active row (also `bg-panel`, left corners only, running to
 * the menu edge) meets it with no gap. Hover rows stay detached pills. `--panel`
 * is a token distinct from `--background` in both light and dark (`--card` is
 * not, in light). This is the layout the real app shell reuses; MainMenu itself
 * stays nav-only.
 */
function MenuShell({
  collapsed,
  onCollapsedChange,
}: {
  collapsed: boolean
  onCollapsedChange?: (collapsed: boolean) => void
}) {
  const [active, setActive] = React.useState("Projects")
  return (
    <div className="flex h-160 overflow-hidden rounded-lg border border-border bg-background">
      <MainMenu
        items={ITEMS}
        activeId={active}
        onSelectItem={(item) => setActive(item.id)}
        collapsed={collapsed}
        onCollapsedChange={onCollapsedChange}
      />
      <ContentPanel>
        <h2 className="font-heading text-xl font-semibold text-fg-strong">
          {active}
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {active} folder placeholder. {PLACEHOLDER}
        </p>
        <Card>
          <CardHeader>
            <CardTitle>This is a Card</CardTitle>
          </CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted-foreground">
            This is a card placeholder. But I must explain to you how all this
            mistaken idea of denouncing pleasure and praising pain was born and I
            will give you a complete account of the system, and expound the
            actual teachings of the great explorer of the truth, the
            master-builder of human happiness.
          </CardContent>
        </Card>
      </ContentPanel>
      {/* remaining stage */}
      <div className="min-w-0 flex-1" />
    </div>
  )
}

export function MenuShowcase() {
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <header className="pb-6">
        <h1 className="font-heading text-2xl font-semibold text-fg-strong">
          Main menu
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          The app-shell navigation — drag the right edge to resize it anywhere
          between the 3rem icon rail and 16rem; release it near the minimum and
          it snaps collapsed. Every icon sits on one fixed axis that never moves.
          A hovered row is a detached pill; the active row takes the panel's fill
          and attaches flush to the content panel beside it. Items are the
          top-level Obsidian vault folders. Hand-built in{" "}
          <span className="font-mono text-xs">
            src/components/sympose/main-menu.tsx
          </span>
          .
        </p>
      </header>

      <div className="mb-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className={cn(
            "inline-flex h-8 items-center rounded-md border border-border bg-card px-3 text-sm font-medium transition-colors hover:bg-accent",
            "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          )}
        >
          {collapsed ? "Expand" : "Collapse"} menu
        </button>
        <span className="font-mono text-xs text-fg-muted">
          collapsed = {String(collapsed)}
        </span>
      </div>

      <MenuShell collapsed={collapsed} onCollapsedChange={setCollapsed} />

      <h2 className="mt-12 font-heading text-lg font-semibold text-fg-strong">
        Both states
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Expanded (icon + label) and collapsed (icon rail). The icon axis and the
        active-row ↔ panel fill match hold in both.
      </p>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <MenuShell collapsed={false} />
        <MenuShell collapsed />
      </div>

      <h2 className="mt-12 font-heading text-lg font-semibold text-fg-strong">
        Folder icons
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
        Reassigned from the design mock so each reads from its name: Daily →
        calendar, Drawings → brush, Limbo → hourglass, Quotes → quotation mark,
        Reading → open book, Recipes → chef hat, Templates → copy. All from{" "}
        <span className="font-mono text-xs">@hugeicons/core-free-icons</span>.
      </p>
    </div>
  )
}
