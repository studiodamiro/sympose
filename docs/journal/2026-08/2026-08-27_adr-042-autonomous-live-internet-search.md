---
title: "ADR-042 — Autonomous Live Internet Search (web_search) & Zero-Key ddgs Standard"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-042 — Autonomous Live Internet Search (`web_search`) & Zero-Key `ddgs` Standard

- **Status:** Accepted — extends
  [ADR-033](./2026-08-26_adr-033-zero-key-native-web-search-ddgs.md) with a
  skill playbook, a `[SEARCH]` action tag, and the anti-helplessness axiom
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Asked for real-time data (crypto prices, online news), agents emitted canned
refusals ("Since I don't have real-time market data access, you might want to
visit an exchange...") — turning the user into the assistant.

## Decision

1. Create `skills/web_search/SKILL.md`; add autonomic `[SEARCH: <query>]` /
   `[WEB_SEARCH: <query>]` tags to `ActionProcessor`.
2. Integrate `ddgs` into `NativeTools.execute("web_search", ...)` — < 0.5 s, $0
   in keys.
3. Add the **Live Internet Access & Anti-Helplessness Axiom** to
   `workspace_rules.md`: canned refusals are banned; agents must dispatch
   `[SEARCH: <query>]` or `[SPAWN_WORKER: web_search | <task>]` and synthesize
   live results in-turn.

## Consequences

**Positive**

- Real-time questions get real answers with live citations, in one turn.
- No API keys or accounts.

**Negative / costs**

- Result quality and rate behaviour depend on `ddgs` / DuckDuckGo, outside
  Sympose's control.

## Alternatives rejected

- **Leaving canned "I can't access the internet" refusals in place.** Rejected
  by the anti-helplessness axiom: the hub exists to do the lookup, not to
  redirect the user.
