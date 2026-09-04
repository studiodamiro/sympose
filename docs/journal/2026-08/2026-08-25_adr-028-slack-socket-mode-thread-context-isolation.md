---
title: "ADR-028 — Slack Socket Mode Integration & Thread Context Isolation"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-028 — Slack Socket Mode Integration & Thread Context Isolation

- **Status:** Accepted — thread-history bleed into the action parser is fixed by
  [ADR-041](./2026-08-27_adr-041-slack-thread-active-context-isolation.md); the
  per-session-id concurrency model is formalised by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md)
  (Standard 4)
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Extending the hub from the local REPL to Slack. HTTP webhooks need open inbound
ports, reverse proxies, or `ngrok` — all violating the zero-infrastructure
mandate. Global per-persona history would bleed context across concurrent
threads. Slack rate limits (~1 update/s/message) rule out character streaming.

## Decision

1. **Zero inbound ports via Socket Mode.** `SlackDaemon` (`sympose/slack.py`)
   uses `slack-bolt` + `SocketModeHandler` over an outbound WebSocket
   (`SLACK_APP_TOKEN` / `SLACK_BOT_TOKEN`).
2. **Thread-bound session isolation.** `thread_id = f"{channel_id}:{thread_ts}"`;
   histories keyed `thread_histories[f"{thread_id}:{handle}"]`.
3. **Persona mention routing.** `@grace`, `@aurelius`, `/switch @grace` route the
   thread; replies inherit the active persona; default `samantha`.
4. **Instant reaction SLA & badging.** Add `eyes` on receipt (< 0.8s), execute
   autonomic tags, convert Markdown to Slack mrkdwn, post the reply, swap the
   reaction to `white_check_mark`.
5. **Strict modularity.** `sympose/slack.py` under the 200 LOC ceiling.

## Consequences

**Positive**

- No firewall changes, no tunnels.
- Concurrent threads and users never cross-contaminate context.
- Immediate visual acknowledgement despite Slack rate limits.

**Negative / costs**

- No live token streaming in Slack — the reply posts once, complete.
- Thread history passed into prompts later caused ghost-action bleed (ADR-041).

## Alternatives rejected

- **HTTP webhook integration (open ports / reverse proxy / `ngrok`).** Rejected:
  inbound exposure and tunnel daemons violate the zero-infrastructure mandate.
- **Global per-persona conversation history.** Rejected: catastrophic context
  bleed across simultaneous Slack threads.
