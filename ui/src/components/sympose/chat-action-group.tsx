import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Bookmark01Icon, BubbleChatAddIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The stage's top-right chat affordances — toggle the chat panel, and
 * bookmark — parked as a sibling of the panels, alongside
 * `<NebulaModeToggle>`, so it stays reachable whether or not chat is open.
 * Same `bg-secondary` chip / `size-7` icon-button recipe as that toggle, for
 * one consistent top-right control cluster. The toggle button's label is
 * "Chat" (matching `<TopBar>`'s identical phone entry point) rather than
 * "New conversation" — its only wired behavior is show/hide, it doesn't
 * reset anything, so the label says exactly what it does.
 */
interface ChatActionGroupProps extends React.ComponentProps<"div"> {
  chatOpen?: boolean
  onToggleChat?: () => void
}

function ChatActionGroup({
  className,
  chatOpen = false,
  onToggleChat,
  ...props
}: ChatActionGroupProps) {
  return (
    <div
      data-slot="chat-action-group"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md bg-secondary p-0.5",
        className
      )}
      {...props}
    >
      <button
        type="button"
        aria-label="Chat"
        aria-pressed={chatOpen}
        onClick={onToggleChat}
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-background aria-pressed:text-foreground"
      >
        <HugeiconsIcon icon={BubbleChatAddIcon} className="size-4" />
      </button>
      <button
        type="button"
        aria-label="Bookmark conversation"
        disabled
        title="Bookmark — coming soon"
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-40"
      >
        <HugeiconsIcon icon={Bookmark01Icon} className="size-4" />
      </button>
    </div>
  )
}

export { ChatActionGroup }
