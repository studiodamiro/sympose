import * as React from "react"

import { cn } from "@/lib/utils"
import { getPersona } from "@/lib/personas"
import { MetaText } from "@/components/sympose/meta-text"
import { ModelChip } from "@/components/sympose/model-chip"
import { PersonaPill } from "@/components/sympose/persona-pill"

/**
 * A blinking caret shown at the tail of a mid-stream assistant message
 * (UI_DESIGN_REFERENCE.md §7 — "show a mid-stream message with a caret").
 */
function StreamingCaret({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="streaming-caret"
      aria-hidden
      className={cn(
        "ml-0.5 inline-block h-[1.1em] w-0.5 translate-y-[0.15em] bg-brand motion-safe:animate-pulse",
        className
      )}
      {...props}
    />
  )
}

/**
 * One turn in the multi-agent chat timeline (UI_DESIGN_REFERENCE.md §7).
 * User turns are right-aligned with a filled bubble; persona turns are a
 * left-aligned identity header (handle pill + model chip + latency) over plain
 * flowing text — distinction by alignment/fill, never chat-bubble kitsch.
 */
interface ChatMessageProps extends React.ComponentProps<"div"> {
  role: "user" | "persona"
  /** Persona handle for `role="persona"`. */
  handle?: string
  timestamp?: string
  /** Latency / TTFT readout, e.g. `0.68s` or `<2ms`. */
  latency?: string
  streaming?: boolean
  /** Action badges + any other footer content, rendered under the message body. */
  footer?: React.ReactNode
}

function ChatMessage({
  className,
  role,
  handle,
  timestamp,
  latency,
  streaming = false,
  footer,
  children,
  ...props
}: ChatMessageProps) {
  const persona = role === "persona" && handle ? getPersona(handle) : undefined

  if (role === "user") {
    return (
      <div
        data-slot="chat-message"
        data-role="user"
        className={cn("flex flex-col items-end gap-1", className)}
        {...props}
      >
        <div className="max-w-[80%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
          {children}
        </div>
        {(timestamp || footer) && (
          <div className="flex items-center gap-2">
            {footer}
            {timestamp && <MetaText>{timestamp}</MetaText>}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      data-slot="chat-message"
      data-role="persona"
      className={cn("flex flex-col gap-1.5", className)}
      {...props}
    >
      <div className="flex flex-wrap items-center gap-2">
        {handle && <PersonaPill handle={handle} size="sm" />}
        {handle && <ModelChip handle={handle} model={persona?.model} />}
        {latency && <MetaText>{latency}</MetaText>}
        {timestamp && <MetaText>· {timestamp}</MetaText>}
      </div>
      <div className="max-w-[74ch] text-sm leading-relaxed text-foreground">
        {children}
        {streaming && <StreamingCaret />}
      </div>
      {footer && <div className="flex flex-wrap gap-1.5 pt-0.5">{footer}</div>}
    </div>
  )
}

export { ChatMessage, StreamingCaret }
