---
entry: 2026-08-26
created: 2026-08-26 16:10
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - multi-agent
  - slack
  - moderation
  - circuit-breaker
  - adr-036
---

# Engineering Journal: Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker (ADR-036)

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace Hopper / Samantha  
> **Status:** APPROVED & IMPLEMENTED (ADR-036)  

---

## 1. Context & Motivation

During multi-agent interactions in Slack, two distinct failure modes emerged:
1. **Single-Agent Roleplay Simulation**: An agent, when asked to discuss a topic with peers, simulated a fake theater script (`**Marcus Aurelius:** ... **Grace Hopper:** ...`) in one single turn rather than engaging in real multi-turn Slack messaging.
2. **Autonomous Runaway Cascades (118 replies in 30 mins)**: Once native inter-agent tagging was enabled, bots triggered each other in an unbounded ping-pong loop, drifting from a simple canvas layout request into writing full database DDL schemas and payment ledger architectures.

---

## 2. Architectural Decisions

- **[ADR-036 — Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker](./2026-08-26_adr-036-multi-agent-collaboration-circuit-breaker.md):**
  real inter-agent messaging, zero roleplay (036.1); Samantha as
  `discussion_moderation` scope anchor + convergence (036.2); the
  `performance.max_consecutive_bot_turns` circuit breaker, default 6 (036.3).
  Rejected single-turn "theater script" simulation and unbounded tagging.

---

## 3. Dynamic User-Agnostic Mention Resolution
* All outgoing `@mentions` (e.g. `@damiro`, `@samantha`, `@grace`) dynamically resolve against Slack's live `users.list` API into native `<@USER_ID>` tags, rendering glowing, clickable blue badges and real Slack notifications with zero hardcoded names.
