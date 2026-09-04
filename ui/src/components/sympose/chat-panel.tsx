import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Bookmark01Icon,
  BubbleChatAddIcon,
  CloudIcon,
  PlusSignIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The chat surface for the app-shell stage — transparent, no chrome of its own.
 * Two jobs:
 *
 * 1. Centre a reading column in whatever width it is handed. The column is
 *    `mx-auto` and capped at `measure` (42rem — the comfortable measure the rest
 *    of the chat UI uses); a wide stage lets the slack fall away evenly so it
 *    sits dead-centre, and a narrow stage (two panels on a tablet) still keeps
 *    a symmetric side gutter so the text never runs flush to the slot edges.
 * 2. Dock the composer. The transcript scrolls; the composer is pinned to the
 *    bottom on the same axis, and a short conversation is bottom-anchored
 *    (`justify-end`) so it hugs the composer.
 *
 * The panel stays mounted; its stage slot animates its own width and opacity as
 * chat opens and closes (see `AppShell`). The composer is a static mock. The
 * stage action group (new conversation / bookmark) is a sibling — see
 * `<ChatActionGroup>` — parked at the stage's top-right so it stays reachable
 * when chat is closed.
 */
interface ChatPanelProps extends React.ComponentProps<"div"> {
  /** Transcript turns — typically `<ChatMessage>` nodes. */
  children?: React.ReactNode
  /** Comfortable reading width for the column. */
  measure?: string
  placeholder?: string
  /** Model label shown in the composer footer chip. */
  model?: string
  /** Phone shell: tighter side gutters, no top gap for a floating action row. */
  compact?: boolean
}

function ChatPanel({
  className,
  children,
  measure = "42rem",
  placeholder = "Ask Samantha.",
  model = "3.7 Flash",
  compact = false,
  style,
  ...props
}: ChatPanelProps) {
  return (
    <div
      data-slot="chat-panel"
      className={cn("flex h-full min-h-0 flex-col", className)}
      style={{ "--chat-measure": measure, ...style } as React.CSSProperties}
      {...props}
    >
      {/* transcript — scrolls; content bottom-anchored to the composer. The
          column is `mx-auto` so it stays centred in whatever width the slot is
          handed; the side padding is a guaranteed symmetric gutter, so even a
          narrow slot (two panels on a tablet, or a phone) reads as a centred
          reading column rather than flush-cramped text. */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          className={cn(
            "mx-auto flex min-h-full w-full max-w-(--chat-measure) flex-col justify-end gap-6",
            compact ? "px-4 pt-6 pb-6" : "px-6 pt-14 pb-8 sm:px-8"
          )}
        >
          {children}
        </div>
      </div>

      {/* composer dock — same column axis + gutter as the transcript */}
      <div className="shrink-0">
        <div
          className={cn(
            "mx-auto w-full max-w-(--chat-measure) pb-6",
            compact ? "px-4" : "px-6 sm:px-8"
          )}
        >
          <div className="rounded-lg border border-border bg-background transition-colors focus-within:border-brand">
            <textarea
              rows={1}
              placeholder={placeholder}
              className="block w-full resize-none bg-transparent px-3.5 py-3 text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div className="mt-2 flex items-center justify-between px-1">
            <button
              type="button"
              aria-label="Add attachment"
              className="grid size-7 place-items-center rounded-full border border-border text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
            >
              <HugeiconsIcon icon={PlusSignIcon} className="size-4" />
            </button>
            <span className="inline-flex h-6 items-center gap-1 rounded-md bg-chip px-2 font-mono text-[11px] text-fg-muted">
              <HugeiconsIcon icon={CloudIcon} className="size-3" />
              {model}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * The stage's top-right action group — new conversation (toggles the chat panel)
 * and bookmark. Rendered as a sibling of the panels, parked at the stage's
 * top-right and metric-aligned to `<MarkdownPanel>`'s toolbar row so the two
 * panels' chrome reads as one line. Stays put whether or not chat is open.
 */
interface ChatActionGroupProps extends React.ComponentProps<"div"> {
  /** Chat panel currently open — drives the new-conversation button's state. */
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
        aria-label="New conversation"
        aria-pressed={chatOpen}
        onClick={onToggleChat}
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none aria-pressed:bg-background aria-pressed:text-foreground"
      >
        <HugeiconsIcon icon={BubbleChatAddIcon} className="size-4" />
      </button>
      <button
        type="button"
        aria-label="Bookmark conversation"
        className="grid size-7 place-items-center rounded-sm text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <HugeiconsIcon icon={Bookmark01Icon} className="size-4" />
      </button>
    </div>
  )
}

export { ChatPanel, ChatActionGroup }
