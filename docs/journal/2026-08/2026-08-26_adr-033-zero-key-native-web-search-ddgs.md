---
title: "ADR-033 — Zero-Key Native Web Search & the ddgs Standard"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-033 — Zero-Key Native Web Search & the `ddgs` Standard

- **Status:** Accepted — amends
  [ADR-013](./2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md) /
  [ADR-032](./2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md) by
  removing the Brave Search MCP server; the action-tag surface is extended by
  [ADR-042](./2026-08-27_adr-042-autonomous-live-internet-search.md)
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

External search providers (Brave Search API, Google Search API) require
developer registration, credit-card validation, and hidden plan tiers; they
create fragile runtime dependencies on expiring tokens and quotas — turning the
user into an API administrator, against the Zero-Maintenance Mandate
([ADR-020](./2026-08-25_adr-020-zero-maintenance-mandate.md)).

## Decision

- **ADR-033.1 — Native zero-key `web_search`.** `web_search(query, max_results)`
  in `sympose/native_tools.py`, powered by `ddgs` (DuckDuckGo) with TLS header
  masking and live URL citations — $0 cost, no keys, no accounts.
- **ADR-033.2 — Direct worker pipeline routing.** `sympose/workers.py` routes
  `web_search` through native execution, no MCP subprocess (< 0.4 s).
- **ADR-033.3 — Two-tier web intelligence.** Tier 1 discovery (`web_search`) →
  Tier 2 deep extraction (`fetch` MCP server scrapes full pages).
- **ADR-033.4 — Deprecate proprietary search keys.** Purge `brave_search` config
  and env vars from `mcp/servers.json(.example)`, `requirements.txt`, docs, and
  skill playbooks.

## Consequences

**Positive**

- Web search works out of the box with zero setup.
- One less subprocess and one less dependency in the tree.

**Negative / costs**

- `ddgs` result quality / rate behaviour is outside Sympose's control (no SLA).

## Alternatives rejected

- **Brave Search API / Google Search API.** Rejected: account registration,
  credit-card validation, expiring API tokens, and rate quotas — operational
  burden that violates the Zero-Maintenance Mandate.
