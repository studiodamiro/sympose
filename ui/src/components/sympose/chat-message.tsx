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
  /**
   * A persona reaction to a user turn (`[REACT]`, UI_DESIGN_REFERENCE.md §7) —
   * pass the glyph only; it is chipped and floated so it straddles the bubble's
   * bottom-left edge. `role="user"` only.
   */
  reaction?: React.ReactNode
}

function ChatMessage({
  className,
  role,
  handle,
  timestamp,
  latency,
  streaming = false,
  footer,
  reaction,
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
        <div
          className={cn(
            "relative max-w-[80%] rounded-tl-lg rounded-br-lg rounded-bl-lg bg-panel px-4 pt-3 text-sm leading-relaxed text-muted-foreground",
            // extra bottom room so the floated reaction chip overlaps the copy,
            // never the reverse; the outer margin reserves layout space for the
            // part of the chip that hangs past the bubble.
            reaction ? "mb-3 pb-7" : "pb-3"
          )}
        >
          {children}
          {reaction && (
            <span className="absolute -bottom-2.5 left-3 inline-flex h-6 items-center gap-1 rounded-md bg-chip px-1.5 text-fg-muted [&_svg]:size-3.5">
              {reaction}
            </span>
          )}
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
      <div className="max-w-[74ch] text-sm leading-relaxed text-muted-foreground">
        {children}
        {streaming && <StreamingCaret />}
      </div>
      {footer && <div className="flex flex-wrap gap-1.5 pt-0.5">{footer}</div>}
    </div>
  )
}

export { ChatMessage, StreamingCaret }
