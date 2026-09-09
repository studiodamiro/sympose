---
title: "ADR-082 — Slack Daemon Heartbeat & Dashboard Status Pill"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - slack
---

# ADR-082 — Slack Daemon Heartbeat & Dashboard Status Pill

- **Status:** Accepted — implemented 2026-09-10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Sits alongside the vault write-back work in
  [ADR-081](./2026-09-10_adr-081-vault-note-write-back.md); same pattern —
  a small backend contract behind a dashboard affordance.

## Context

`sympose --slack` and `sympose --dashboard` are separate processes with no IPC.
There was no way, from the dashboard or anywhere else, to see whether the Slack
Socket Mode daemon was running or how current its code was — you had to
`ps aux | grep sympose` on the host. A stale daemon (still running last week's
build after a `git pull`) looked identical to a healthy one.

The ask was a **read-only** indicator at the bottom of the Settings panel — a
small status pill on the left, a compact light/dark switch on the right, both at
the height of the editor panel's `[[link]]` pills. Explicitly **not** a
start/stop control: making the password-gated web server a process supervisor
for a persistent background daemon is a much larger surface (detach semantics,
PID/lock files, orphan cleanup, the security posture of "web button spawns a
daemon") and would need its own ADR against the zero-bloat posture.

## Decision

**The daemon writes a heartbeat file into the workspace; the dashboard reads
its age.**

### Backend

1. **`sympose/slack_heartbeat.py`** — a stdlib-only leaf module.
   - `write_heartbeat(workspace_dir, personas)` — atomic
     (write-temp-then-`os.replace`) write of
     `{"ts": <epoch>, "pid": <int>, "personas": [...]}` to
     `<workspace_dir>/.slack_heartbeat.json`. Best-effort; a write failure never
     propagates.
   - `clear_heartbeat(workspace_dir)` — unlink, for a clean exit.
   - `read_status(workspace_dir)` → `{state, last_seen, age_seconds, personas,
     pid}`. `state` is `connected` (age ≤ 45s), `stale` (≤ 120s), or `offline`
     (older, missing, or unreadable). `last_seen` survives into `offline` so the
     UI can still say "last heartbeat 6m ago".
   - Thresholds `WRITE_INTERVAL = 15`, `STALE_AFTER = 45`, `OFFLINE_AFTER = 120`
     — roughly 1 : 3 : 8, so a single skipped write never reads as a dead
     daemon.
2. **`MultiAgentSlackRunner.run_all`** gains `workspace_dir`. When set, it
   stamps the heartbeat immediately, registers `clear_heartbeat` with `atexit`,
   and spawns one `daemon=True` thread that re-stamps every `WRITE_INTERVAL`s.
   `app.py` passes the already-resolved `workspace_dir`.
3. **`GET /api/slack/status`** returns `read_status(workspace_dir)`, behind the
   same ADR-064.1 password guard as every route. `create_app` takes an optional
   `workspace_dir` (defaulting to `resolve_workspace_dir()`, so existing
   test callers and `run_server` both work).

### Frontend

4. **`fetchSlackStatus()` / `useSlackStatus()`** — polls `/api/slack/status`
   every 12s while mounted. A dashboard-unreachable fetch yields
   `state: "unknown"`, distinct from `"offline"`, so the pill can tell "Slack is
   down" from "I can't tell". The hook is mounted only in the Settings footer,
   so the poll stops when that panel is closed.
5. **`<SlackStatusPill>`** — the editor `[[link]]` pill geometry
   (`rounded-full border px-2.5 py-1 text-xs`) with a status dot: `--ok` green
   when connected, amber `--chip-foreground` when unresponsive, muted when
   offline/unknown. Heartbeat age and served personas go in the `title`.
6. **`<ThemeToggle>`** — a pill-height light/dark switch. Reads the effective
   theme from the `dark` / `light` class `ThemeProvider` writes on `<html>`
   (via a `MutationObserver`), so `system` resolves correctly; clicking always
   sets an explicit `light` / `dark`. The three-way `light / dark / system`
   control still lives in the dev-harness header.
7. Both sit in a `mt-auto border-t` footer at the bottom of the Settings
   panel — pinned, so the status is visible whenever Settings is open.

## Consequences

- The dashboard (and anything else) can see Slack liveness without `ps`. A
  daemon that crashed or is running stale code shows `offline` within two
  minutes.
- The daemon does one extra small file write every 15s. No new dependency, no
  new service — a thread on an existing process.
- `.slack_heartbeat.json` is per-workspace runtime state, git-ignored like
  `.certs/` and `.vault_index/`.
- Still no control from the web UI. Restarting Slack remains a terminal action
  (or an OS supervisor — `launchd`/systemd — which is the right tool for
  "restart on deploy").
- A hung daemon that still writes heartbeats reads as `connected`. Catching a
  process that is alive but not actually servicing Socket Mode events would
  need the heartbeat to be driven by the event loop rather than a wall-clock
  timer — deferred until there's evidence that failure mode happens.

## Alternatives rejected

- **Full start/stop toggle in the dashboard.** Turns the FastAPI server into a
  process supervisor: subprocess spawn/detach, PID/lock files, orphan cleanup,
  and a password-gated "launch a persistent daemon" button. Large surface,
  its own ADR, and against the "few moving parts" posture. The pain point was
  visibility, not control.
- **PID file + `os.kill(pid, 0)` liveness.** Lighter (no timer), but a
  hung/zombie process still reads as running, and an unclean exit leaves a
  stale PID file that then needs its own staleness heuristic — at which point
  it is a worse heartbeat. The timestamped heartbeat is honest about "when did
  I last hear from it".
- **Scan the process table** (`psutil` / `pgrep -f "sympose --slack"`). A new
  dependency or a shell-out, platform-specific, and matches on a command-line
  substring that a wrapper or a renamed entrypoint breaks.
- **A shared socket / HTTP ping from dashboard to daemon.** The daemon has no
  server; adding one (a port to bind, to firewall, to auth) is far more than a
  status line needs.
- **Heartbeat driven by Slack events instead of a timer.** More accurate about
  "is it actually working", but a quiet channel would then read as offline. A
  wall-clock beat answers "is the process alive" cleanly; event-driven
  liveness can layer on later if needed.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
