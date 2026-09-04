---
title: "ADR-036 — Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-036 — Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker

- **Status:** Accepted
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace and Samantha (Engineering Partners)

## Context

Two failure modes in Slack multi-agent interactions: (1) an agent asked to
"discuss with peers" wrote a fake one-turn theater script for everyone; (2) once
native inter-agent tagging was live, bots triggered each other in an unbounded
ping-pong (118 replies in 30 minutes), drifting from a canvas layout into DDL
schemas and payment ledgers.

## Decision

- **ADR-036.1 — Real inter-agent messaging, zero roleplay.** An agent speaks
  only for itself and `@mentions` the peer with a focused question; writing a
  peer's dialogue is forbidden.
- **ADR-036.2 — Samantha as discussion moderator (`discussion_moderation`
  skill).** Scope anchor (cut off scope bloat) and cognitive convergence
  (timebox to 1–3 high-signal exchanges, then synthesize a 4-part deliverable).
- **ADR-036.3 — Safety circuit breaker
  (`performance.max_consecutive_bot_turns`, default 6).** `sympose/slack.py`
  tracks all workspace `bot_user_ids`; at the threshold Samantha synthesizes the
  final plan, stops tagging bots, and yields to the human; specialists halt
  silently.

Outgoing `@mentions` resolve against Slack's live `users.list` into
`<@USER_ID>` tags — real notifications, zero hardcoded names.

## Consequences

**Positive**

- Genuine multi-turn collaboration instead of simulated scripts.
- Runaway cascades are bounded and always return the floor to the human.

**Negative / costs**

- A hard turn cap can cut off a debate that legitimately needed one more
  exchange — the moderator must synthesize from what it has.

## Alternatives rejected

- **Single-turn simulated multi-agent "theater script".** Rejected: not real
  collaboration; no peer autonomy or genuine exchange.
- **Unbounded inter-agent tagging with no breaker.** Rejected: demonstrated
  runaway cascade and scope explosion.
