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

## 2. Architectural Decisions (ADR-036)

### ADR-036.1: Real Inter-Agent Messaging & Zero Roleplay Simulation
* Agents are strictly forbidden from writing dialogue lines for their peers.
* Each agent speaks solely for itself, state its perspective, and explicitly `@mentions` the other agent with focused questions in Slack.

### ADR-036.2: Samantha as Discussion Moderator (`discussion_moderation` Skill)
* Samantha is established as the Master Strategic Moderator:
  * **Scope Anchor**: Anchors discussions to the exact user request and cuts off scope bloat (e.g. preventing database coding when only a canvas was requested).
  * **Cognitive Convergence**: Evaluates information sufficiency and timeboxes debates to 1–3 high-signal exchanges before synthesizing a clean 4-part deliverable for the user.

### ADR-036.3: Multi-Agent Safety Circuit Breaker (`performance.max_consecutive_bot_turns`)
* In [`sympose/slack.py`](../../sympose/slack.py), the daemon maintains a live set of all workspace bot IDs (`bot_user_ids`).
* If consecutive bot-to-bot replies in a thread reach the safety threshold (default: `6`), Samantha steps in to synthesize the final plan, stops tagging other bots, and yields the floor back to the human. Specialist bots halt silently.

---

## 3. Dynamic User-Agnostic Mention Resolution
* All outgoing `@mentions` (e.g. `@damiro`, `@samantha`, `@grace`) dynamically resolve against Slack's live `users.list` API into native `<@USER_ID>` tags, rendering glowing, clickable blue badges and real Slack notifications with zero hardcoded names.
