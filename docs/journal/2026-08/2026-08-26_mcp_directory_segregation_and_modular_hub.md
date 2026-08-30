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

## 2. Architectural Decisions (ADR-032)

### ADR-032.1: First-Class `mcp/` Directory Hierarchy
* Created a root-level `mcp/` folder containing:
  * [`mcp/servers.json`](../../../mcp/servers.json): Master server definitions (`fetch`, `filesystem`, `github`, `slack`, `brave_search`).
  * [`mcp/servers.json.example`](../../../mcp/servers.json.example): Tracked template for fresh repository clones.
  * [`mcp/README.md`](../../../mcp/README.md): Documentation on configuring standard and custom local MCP servers.

### ADR-032.2: Dual-Module Engine Split (<200 LOC Ceiling)
* Extracted `MCPClient` into [`sympose/mcp_client.py`](../../../sympose/mcp_client.py) (176 LOC).
* Maintained `MCPRegistry` in [`sympose/mcp.py`](../../../sympose/mcp.py) (106 LOC).
* Implemented automatic discovery in `MCPRegistry.auto_discover()` to scan `mcp/servers.json` on startup with fallback support for legacy `config.yaml`.

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
