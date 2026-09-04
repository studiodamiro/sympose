---
title: "ADR-032 — First-Class mcp/ Directory Hierarchy & Modular Hub Refactor"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-032 — First-Class `mcp/` Directory Hierarchy & Modular Hub Refactor

- **Status:** Accepted — amends
  [ADR-013](./2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md) by
  moving MCP config out of `config.yaml` into a dedicated `mcp/` tree and
  splitting the client into its own module
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

MCP servers were configured inside `config.yaml`, while `skills/` and
`profiles/` each had a dedicated top-level directory. External tool integrations
lacked the same first-class status.

## Decision

- **ADR-032.1 — First-class `mcp/` directory.** `mcp/servers.json` (master
  definitions), `mcp/servers.json.example` (tracked template),
  `mcp/README.md` (configuration docs).
- **ADR-032.2 — Dual-module engine split.** Extract `MCPClient` into
  `sympose/mcp_client.py`; keep `MCPRegistry` in `sympose/mcp.py`;
  `MCPRegistry.auto_discover()` scans `mcp/servers.json` on startup with a
  legacy `config.yaml` fallback.

## Consequences

**Positive**

- MCP config has the same organisational standing as skills and profiles.
- Both modules stay under the 200 LOC ceiling.

**Negative / costs**

- Two config locations during the fallback window (`mcp/servers.json` +
  legacy `config.yaml`).

  > **Note:** the `brave_search` server registered in `mcp/servers.json` here was
  > later purged by
  > [ADR-033](./2026-08-26_adr-033-zero-key-native-web-search-ddgs.md) in favour
  > of the zero-key `ddgs` standard.

## Alternatives rejected

> Not captured in the original decision record.
