export type SlackState = "connected" | "stale" | "offline" | "unknown"

export interface SlackStatus {
  state: SlackState
  /** Epoch seconds of the daemon's last heartbeat, or `null` if it never ran. */
  lastSeen: number | null
  /** Persona handles the daemon is serving; empty unless `connected` / `stale`. */
  personas: string[]
}

const UNKNOWN: SlackStatus = { state: "unknown", lastSeen: null, personas: [] }

/**
 * Client for `GET /api/slack/status` — liveness of the `sympose --slack`
 * daemon, read from its workspace heartbeat file (ADR-082). Returns
 * `state: "unknown"` when the dashboard API itself is unreachable, so the pill
 * can distinguish "Slack is down" from "I can't tell".
 */
export async function fetchSlackStatus(): Promise<SlackStatus> {
  try {
    const res = await fetch("/api/slack/status")
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = (await res.json()) as {
      state?: SlackState
      last_seen?: number | null
      personas?: string[]
    }
    return {
      state: body.state ?? "unknown",
      lastSeen: body.last_seen ?? null,
      personas: body.personas ?? [],
    }
  } catch {
    return UNKNOWN
  }
}
