import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import { FolderOpenIcon, Settings01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { Logo } from "@/components/logo"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ChatActionGroup } from "./chat-panel"

/**
 * The phone-only shell header. On desktop / tablet the brand mark, the vault
 * navigation, Settings, and the account all live inside `<MainMenu>`; a phone
 * has no room for a persistent menu, so those move up here into one fixed row
 * that is present in every view:
 *
 *   [hex] Sympose ............. [ new-chat · bookmark ] [ vault ] [ cog ] [ @ ]
 *
 * The `Sympose` wordmark is the first thing to drop when the row gets tight.
 * `vault` slides the menu rail in and out (see `AppShell`); the chat action
 * group is the same component the desktop stage floats top-right.
 */
interface TopBarProps extends React.ComponentProps<"header"> {
  account?: { name: string }
  chatOpen?: boolean
  onToggleChat?: () => void
  /** Vault button — pressed while the menu rail is showing. */
  menuOpen?: boolean
  onToggleMenu?: () => void
  settingsActive?: boolean
  onSettings?: () => void
  accountActive?: boolean
  onAccount?: () => void
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
  account = { name: "Agent" },
  chatOpen = false,
  onToggleChat,
  menuOpen,
  onToggleMenu,
  settingsActive,
  onSettings,
  accountActive,
  onAccount,
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
      <Logo className="size-6 shrink-0" />
      {/* wordmark is the first thing to drop when the row gets tight */}
      <span className="hidden text-base font-semibold tracking-tight min-[380px]:inline">
        Sympose
      </span>

      <div className="ms-auto flex items-center gap-1">
        <ChatActionGroup chatOpen={chatOpen} onToggleChat={onToggleChat} />
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
