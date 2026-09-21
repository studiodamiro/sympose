import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Add01Icon, Tick02Icon } from "@hugeicons/core-free-icons"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Vault } from "@/lib/vaults-api"

/**
 * Slack-style workspace switcher, hung off the brand mark (Logo + vault-name
 * wordmark) in both `<TopBar>` (phone) and `<MainMenu>` (tablet/desktop) —
 * VISION.md's Multi-vault section: one active vault at a time, switched here
 * rather than in Settings. `children` is the brand-mark markup itself (icon
 * and/or wordmark); this component only supplies the click target and the
 * popup, so both hosts keep their own layout.
 *
 * Always interactive, even with zero or one configured vaults — the add-path
 * input below the list is how a first or second vault gets configured at
 * all, not just how an existing set gets switched between (ADR 004).
 */
function WorkspaceSwitcher({
  vaults,
  active,
  onSwitch,
  onAdd,
  triggerClassName,
  align = "start",
  children,
}: {
  vaults: Vault[]
  active: string | null
  onSwitch: (path: string) => void
  /** Add a new vault by absolute path. Resolves `true` on success (the
   *  input clears); `false` leaves the typed path in place so it can be
   *  corrected — the caller is expected to toast the reason via `notify`. */
  onAdd: (path: string) => Promise<boolean>
  triggerClassName?: string
  align?: "start" | "center" | "end"
  children: React.ReactNode
}) {
  const [open, setOpen] = React.useState(false)
  const [newPath, setNewPath] = React.useState("")
  const [adding, setAdding] = React.useState(false)

  const submit = async () => {
    const path = newPath.trim()
    if (!path || adding) return
    setAdding(true)
    const ok = await onAdd(path)
    setAdding(false)
    if (ok) {
      setNewPath("")
      setOpen(false)
    }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger aria-label="Switch vault" className={triggerClassName}>
        {children}
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="w-auto min-w-64">
        {vaults.map((vault) => (
          <DropdownMenuItem
            key={vault.path}
            onClick={() => vault.path !== active && onSwitch(vault.path)}
          >
            <span className="min-w-0 flex-1 truncate">{vault.name}</span>
            {vault.path === active && (
              <HugeiconsIcon icon={Tick02Icon} className="shrink-0" />
            )}
          </DropdownMenuItem>
        ))}
        {vaults.length > 0 && <DropdownMenuSeparator />}
        <div
          className="flex items-center gap-1.5 px-1 py-1"
          // Keeps the menu's own roving-focus / typeahead handling (arrow
          // keys, Enter-selects-highlighted-item) from intercepting typing
          // and Enter meant for this plain input instead — same pattern as
          // the vault tree's inline-rename field in `vault-row-menu.tsx`.
          onKeyDown={(e) => e.stopPropagation()}
        >
          <input
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="/path/to/vault"
            aria-label="Vault path to add"
            disabled={adding}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                void submit()
              }
            }}
            className="h-7 min-w-0 flex-1 rounded-md border border-border bg-card px-2 text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          />
          <button
            type="button"
            aria-label="Add vault"
            disabled={adding || !newPath.trim()}
            onClick={() => void submit()}
            className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            <HugeiconsIcon icon={Add01Icon} className="size-4" />
          </button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { WorkspaceSwitcher }
