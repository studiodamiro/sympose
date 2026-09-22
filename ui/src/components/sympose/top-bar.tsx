import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import { FolderOpenIcon, Settings01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { Logo } from "@/components/logo"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { WorkspaceSwitcher } from "@/components/sympose/workspace-switcher"
import { EMPTY_VAULTS, type Vault } from "@/lib/vaults-api"

/**
 * The phone-only shell header. On desktop / tablet the brand mark, the vault
 * navigation, Settings, and the account all live inside `<MainMenu>`; a phone
 * has no room for a persistent menu, so those move up here into one fixed row
 * that is present in every view:
 *
 *   [hex] Sympose ..................... [ vault ] [ cog ] [ @ ]
 *
 * The `Sympose` wordmark is the first thing to drop when the row gets tight.
 * `vault` slides the menu rail in and out (see `AppShell`).
 */

interface TopBarProps extends React.ComponentProps<"header"> {
  account?: { name: string }
  /** Vault button — pressed while the menu rail is showing. */
  menuOpen?: boolean
  onToggleMenu?: () => void
  settingsActive?: boolean
  onSettings?: () => void
  accountActive?: boolean
  onAccount?: () => void
  /** The workspace switcher hung off the brand mark — see `<WorkspaceSwitcher>`
   *  and `main-menu.tsx`'s desktop-rail counterpart. `vaultLabel` is the
   *  wordmark text: the active vault's name when known, else "Sympose". */
  vaults?: Vault[]
  activeVault?: string | null
  onSwitchVault?: (path: string) => void
  onAddVault?: (path: string) => Promise<boolean>
  vaultLabel?: string
}

function IconButton({
  icon,
  label,
  pressed,
  onClick,
}: {
  icon: IconSvgElement
  label: string
  pressed?: boolean
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      onClick={onClick}
      className="grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-accent aria-pressed:text-foreground"
    >
      <HugeiconsIcon icon={icon} className="size-4.5" />
    </button>
  )
}

function TopBar({
  className,
  account = { name: "Persona" },
  menuOpen,
  onToggleMenu,
  settingsActive,
  onSettings,
  accountActive,
  onAccount,
  vaults = EMPTY_VAULTS,
  activeVault = null,
  onSwitchVault,
  onAddVault,
  vaultLabel = "Sympose",
  ...props
}: TopBarProps) {
  return (
    <header
      data-slot="top-bar"
      className={cn(
        "flex h-14 shrink-0 items-center gap-2 bg-background px-3 text-foreground",
        className
      )}
      {...props}
    >
      <WorkspaceSwitcher
        vaults={vaults}
        active={activeVault}
        onSwitch={onSwitchVault ?? (() => {})}
        onAdd={onAddVault ?? (async () => false)}
        align="start"
        triggerClassName="flex min-w-0 flex-1 items-center gap-2 rounded-md py-1 pr-2 -my-1 text-left text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none data-popup-open:text-foreground"
      >
        <Logo className="size-6 shrink-0" />
        {/* wordmark is the first thing to drop when the row gets tight */}
        <span className="hidden min-w-0 truncate text-base font-semibold tracking-tight min-[380px]:inline">
          {vaultLabel}
        </span>
      </WorkspaceSwitcher>

      <div className="ms-auto flex items-center gap-1">
        <div className="flex items-center gap-0.5">
          <IconButton
            icon={FolderOpenIcon}
            label="Vault"
            pressed={menuOpen}
            onClick={onToggleMenu}
          />
          <IconButton
            icon={Settings01Icon}
            label="Settings"
            pressed={settingsActive}
            onClick={onSettings}
          />
          <button
            type="button"
            aria-label={account.name}
            aria-pressed={accountActive}
            onClick={onAccount}
            className="grid size-8 place-items-center rounded-md transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-accent"
          >
            <Avatar size="sm">
              <AvatarFallback className="bg-accent text-[11px] font-medium uppercase">
                {account.name.slice(0, 1)}
              </AvatarFallback>
            </Avatar>
          </button>
        </div>
      </div>
    </header>
  )
}

export { TopBar }
