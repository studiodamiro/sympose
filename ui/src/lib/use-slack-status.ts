import * as React from "react"

import { fetchSlackStatus, type SlackStatus } from "@/lib/slack-status-api"

/** How often to re-poll `/api/slack/status` while the hook is mounted (ms). */
const POLL_INTERVAL = 12_000

/**
 * Polls the Slack daemon's liveness (ADR-082) on a fixed interval while
 * mounted — read-only, no control. Starts `"unknown"` until the first response.
 * Only mount this where the status is actually shown (the Settings footer), so
 * the poll stops when that panel is closed.
 */
export function useSlackStatus(): SlackStatus {
  const [status, setStatus] = React.useState<SlackStatus>({
    state: "unknown",
    lastSeen: null,
    personas: [],
  })

  React.useEffect(() => {
    let alive = true
    const tick = () =>
      fetchSlackStatus().then((next) => {
        if (alive) setStatus(next)
      })
    tick()
    const id = window.setInterval(tick, POLL_INTERVAL)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  return status
}
