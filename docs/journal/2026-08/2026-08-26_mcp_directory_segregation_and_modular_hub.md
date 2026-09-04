---
entry: 2026-08-26
created: 2026-08-26 05:48
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - mcp/servers
  - architecture/modular-hub
  - adr-032
---

# Engineering Journal: First-Class MCP Directory & Modular Hub Refactor

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Status:** APPROVED & IMPLEMENTED (ADR-032)  

---

## 1. Context & Architectural Realignment

Sympose previously configured Model Context Protocol (MCP) servers inside `config.yaml`. However, while prompt playbooks enjoyed a dedicated top-level directory (`skills/`), external tool integrations lacked symmetrical first-class status.

To elevate MCP tools to the same organizational standard as `profiles/` and `skills/`, we segregated MCP into a dedicated **`mcp/`** directory.

---

## 2. Architectural Decisions

- **[ADR-032 — First-Class `mcp/` Directory Hierarchy & Modular Hub Refactor](./2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md):**
  a root `mcp/` tree (`servers.json`, `.example`, `README.md`) (032.1) and a
  dual-module split — `MCPClient` → `sympose/mcp_client.py`, `MCPRegistry` in
  `sympose/mcp.py` with `auto_discover()` (032.2). Amends
  [ADR-013](./2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md).

---

## 3. The Sympose Quad-Directory Standard

```text
sympose/
├── profiles/          # Agent Souls, YAML Manifests, and Memories
├── skills/            # Procedural Prompt Playbooks (SKILL.md)
├── mcp/               # MCP Configuration (servers.json) & Custom Tools
└── docs/              # Architectural Decision Records & Guides
```

---

## 4. Verification & Status

```bash
# 1. MCP Registry Auto-Discovery Test:
Discovered MCP Servers from mcp/: ['fetch', 'filesystem', 'github', 'slack', 'brave_search']
  • [fetch]: npx -y @modelcontextprotocol/server-fetch
  • [filesystem]: npx -y @modelcontextprotocol/server-filesystem .
  • [github]: npx -y @modelcontextprotocol/server-github
  • [slack]: npx -y @modelcontextprotocol/server-slack
  • [brave_search]: npx -y @modelcontextprotocol/server-brave-search

# 2. LOC Verification:
  106 sympose/mcp.py
  176 sympose/mcp_client.py
```
