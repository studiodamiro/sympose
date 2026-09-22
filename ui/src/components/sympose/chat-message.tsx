import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals } from "@/lib/personas"
import type { ChatAction } from "@/lib/chat-mock-data"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ModelChip } from "@/components/sympose/model-chip"
import { ActionBadge } from "@/components/sympose/action-badge"

/** A blinking caret at the tail of a mid-stream persona reply. */
function StreamingCaret({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden
      className={cn(
        "ml-0.5 inline-block h-[1.1em] w-0.5 translate-y-[0.15em] bg-brand motion-safe:animate-pulse",
        className
      )}
      {...props}
    />
  )
}

interface ChatMessageProps extends React.ComponentProps<"div"> {
  role: "user" | "persona"
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  /** Persona's own model string, for the model chip — `role: "persona"` only. */
  model?: string
  timestamp?: string
  streaming?: boolean
  actions?: ChatAction[]
}

/**
 * One turn in the chat transcript. User turns are a right-aligned filled
 * bubble; persona turns are a left-aligned identity header (avatar + name +
 * model chip) over plain flowing text — distinction by alignment, not by two
 * different bubble styles.
 */
function ChatMessage({
  className,
  role,
  handle,
  model,
  timestamp,
  streaming = false,
  actions,
  children,
  ...props
}: ChatMessageProps) {
  if (role === "user") {
    return (
      <div
        data-slot="chat-message"
        data-role="user"
        className={cn("flex flex-col items-end gap-1", className)}
        {...props}
      >
        <div className="max-w-[80%] rounded-tl-lg rounded-br-lg rounded-bl-lg bg-panel px-4 py-3 text-sm leading-relaxed text-muted-foreground">
          {children}
        </div>
        {timestamp && (
          <span className="font-mono text-xs text-fg-muted tabular-nums">
            {timestamp}
          </span>
        )}
      </div>
    )
  }

  const visuals = resolvePersonaVisuals(handle ?? "")

  return (
    <div
      data-slot="chat-message"
      data-role="persona"
      className={cn("flex flex-col gap-1.5", className)}
      {...props}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Avatar size="sm">
          <AvatarFallback
            className="text-background"
            style={{ background: visuals.accent }}
          >
            <HugeiconsIcon icon={visuals.icon} className="size-3.5" />
          </AvatarFallback>
        </Avatar>
        {model && <ModelChip model={model} />}
        {timestamp && (
          <span className="font-mono text-xs text-fg-muted tabular-nums">
            {timestamp}
          </span>
        )}
      </div>
      <div className="max-w-[74ch] text-sm leading-relaxed text-muted-foreground">
        {children}
        {streaming && <StreamingCaret />}
      </div>
      {actions && actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {actions.map((a, i) => (
            <ActionBadge key={i} action={a.kind} detail={a.detail} />
          ))}
        </div>
      )}
    </div>
  )
}

export { ChatMessage, StreamingCaret }
