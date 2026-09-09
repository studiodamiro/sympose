import { cn } from "@/lib/utils"
import { useSlackStatus } from "@/lib/use-slack-status"
import type { SlackState } from "@/lib/slack-status-api"

/**
 * Read-only liveness of the `sympose --slack` daemon (ADR-082), shown in the
 * Settings footer. Same geometry as the editor panel's `[[link]]` pills
 * (`rounded-full border px-2.5 py-1 text-xs`) so the two rows sit at one
 * height. The dashboard cannot start or stop the daemon — this only reports.
 */

const STATE_STYLES: Record<SlackState, { pill: string; dot: string; label: string }> = {
  connected: {
    pill: "border-ok/40 text-ok",
    dot: "bg-ok",
    label: "Slack connected",
  },
  stale: {
    pill: "border-chip-foreground/40 text-chip-foreground",
    dot: "bg-chip-foreground",
    label: "Slack unresponsive",
  },
  offline: {
    pill: "border-border text-muted-foreground",
    dot: "bg-fg-muted",
    label: "Slack offline",
  },
  unknown: {
    pill: "border-border text-fg-muted",
    dot: "bg-fg-muted/50",
    label: "Slack status unknown",
  },
}

function relativeSince(epochSeconds: number | null): string | undefined {
  if (epochSeconds == null) return undefined
  const secs = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds))
  if (secs < 60) return `last heartbeat ${secs}s ago`
  const mins = Math.round(secs / 60)
  if (mins < 60) return `last heartbeat ${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `last heartbeat ${hrs}h ago`
  return `last heartbeat ${Math.round(hrs / 24)}d ago`
}

function SlackStatusPill({ className }: { className?: string }) {
  const { state, lastSeen, personas } = useSlackStatus()
  const style = STATE_STYLES[state]
  const title = [
    relativeSince(lastSeen),
    personas.length > 0 ? `serving ${personas.join(", ")}` : undefined,
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <span
      data-slot="slack-status-pill"
      data-state={state}
      title={title || undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs",
        style.pill,
        className
      )}
    >
      <span className={cn("size-1.5 shrink-0 rounded-full", style.dot)} />
      {style.label}
    </span>
  )
}

export { SlackStatusPill }
