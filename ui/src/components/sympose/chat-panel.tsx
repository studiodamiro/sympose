import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { CloudIcon, PlusSignIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * The chat surface that fills the "stage" — the empty space left of the
 * viewport once `<MainMenu>` and `<ContentPanel>` have taken their widths
 * (see the wireframe). It owns no chrome of its own: transparent background,
 * no border. Two jobs only —
 *
 * 1. Centre a single reading column in whatever space it is handed. The column
 *    is `mx-auto` and capped at `measure` (default 42rem — the comfortable
 *    reading width the rest of the chat UI already uses). On a wide stage the
 *    slack falls away evenly on both sides, so the column sits dead-centre of
 *    the empty space; on a narrow stage the cap yields and the column runs the
 *    full width, held off the edges only by its gutter (`px`).
 * 2. Dock the composer. The transcript scrolls; the composer stays pinned to
 *    the bottom on the same column axis. A short conversation is bottom-anchored
 *    (`justify-end`) so it hugs the composer rather than floating at the top.
 *
 * The composer here is a static mock — swap in `<Composer>` once its chrome
 * (mention hint, ⌘↵ affordance) is reconciled with this layout.
 */
interface ChatPanelProps extends React.ComponentProps<"div"> {
  /** Transcript turns — typically `<ChatMessage>` nodes. */
  children?: React.ReactNode
  /** Comfortable reading width for the column. */
  measure?: string
  placeholder?: string
  /** Model label shown in the composer footer chip. */
  model?: string
}

function ChatPanel({
  className,
  children,
  measure = "42rem",
  placeholder = "Ask Samantha.",
  model = "3.7 Flash",
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
      {/* transcript — scrolls; content bottom-anchored to the composer */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-(--chat-measure) flex-col justify-end gap-6 px-4 py-8 sm:px-6">
          {children}
        </div>
      </div>

      {/* composer dock — same column axis, pinned to the bottom */}
      <div className="shrink-0">
        <div className="mx-auto w-full max-w-(--chat-measure) px-4 pb-6 sm:px-6">
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

export { ChatPanel }
