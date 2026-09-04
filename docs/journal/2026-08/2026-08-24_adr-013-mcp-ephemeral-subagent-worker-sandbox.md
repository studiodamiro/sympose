---
title: "ADR-013 — Model Context Protocol & Ephemeral Sub-Agent Worker Sandbox"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-013 — Model Context Protocol (MCP) & Ephemeral Sub-Agent Worker Sandbox

- **Status:** Accepted — the client is split into its own module by
  [ADR-032](./2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md) and
  its threading model is hardened by
  [ADR-065](./2026-08-30_adr-065-mcp-client-threading-logging-standard.md)
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Dumping ~50 tool schemas into a primary conversational agent costs 5,000+ tokens
per turn and pollutes history with raw terminal / JSON output.

## Decision

Adopt the supervisor–worker pattern over MCP (Model Context Protocol):

- `sympose/mcp.py` — a standard-library JSON-RPC 2.0 client over `stdio`
  subprocesses to local / community MCP servers (filesystem, GitHub, Brave
  Search).
- `sympose/workers.py` — `WorkerEngine` runs an isolated multi-turn tool loop;
  worker context and child processes are freed on completion.
- Autonomic tag `[SPAWN_WORKER: <skill_or_mcp> | <task>]` in
  `sympose/actions.py`.
- Knob `performance.max_worker_tool_turns: 8` in `config.yaml`.

## Consequences

**Positive**

- Primary agents keep a lean prompt and a clean conversation history.
- Tool work is disposable and sandboxed.

**Negative / costs**

- Subprocess lifecycles must be managed (orphan cleanup added by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md)).
- The Brave Search server is later removed in favour of the zero-key `ddgs`
  standard ([ADR-033](./2026-08-26_adr-033-zero-key-native-web-search-ddgs.md)).

## Alternatives rejected

- **Dumping all tool schemas into every primary agent.** Rejected: 5,000+ tokens
  per turn and history pollution with raw tool output.
