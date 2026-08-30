---
entry: 2026-08-26
created: 2026-08-26 06:12
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - search/zero-key
  - native-tools
  - ddgs
  - adr-033
---

# Engineering Journal: Zero-Key Native Web Search & DDGS Standard

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Status:** APPROVED & IMPLEMENTED (ADR-033)  

---

## 1. Context & Motivation

During toolchain evaluation, external search providers (e.g. Brave Search API, Google Search API) presented significant operational friction for local-first assistant workflows:
* Required developer registration, credit card validation, and hidden plan activation tiers.
* Created fragile runtime dependencies on expiring API tokens and rate-limited quotas.
* Violated Sympose's **Zero-Maintenance Mandate** by forcing the user into the role of an API administrator.

To ensure frictionless out-of-the-box operation, we engineered a native, zero-key internet search tool powered by DuckDuckGo (`ddgs`) directly inside Sympose's native execution layer.

---

## 2. Architectural Decisions (ADR-033)

### ADR-033.1: Native Zero-Key Search Tool (`web_search`)
* Implemented `web_search(query, max_results)` directly in [`sympose/native_tools.py`](../../../sympose/native_tools.py).
* Powered by `ddgs` with standard TLS header masking and live URL citation formatting.
* **$0.00 cost, zero API keys, and zero account requirements.**

### ADR-033.2: Direct Worker Pipeline Routing
* Updated [`sympose/workers.py`](../../../sympose/workers.py) to route `web_search` through deterministic native execution without requiring an external MCP subprocess.
* Sub-agent workers execute search queries in sub-second timeframes (<0.4s) and synthesize findings with live citations.

### ADR-033.3: Two-Tier Web Intelligence Pipeline
* **Tier 1 (Discovery):** `web_search` finds articles, documentation links, and breaking news.
* **Tier 2 (Deep Extraction):** `fetch` (`uvx mcp-server-fetch`) downloads and scrapes full markdown pages from discovered URLs.

### ADR-033.4: Complete Deprecation of Proprietary Search Keys
* Purged `brave_search` configurations and environment variables across:
  * [`mcp/servers.json`](../../../mcp/servers.json)
  * [`mcp/servers.json.example`](../../../mcp/servers.json.example)
  * [`requirements.txt`](../../../requirements.txt)
  * Documentation and skill playbooks.

---

## 3. Verification & Live Results

```bash
# 1. Direct Native Execution Test:
NativeTools.execute("web_search", {"query": "Python 3.13 release highlights"})
# Output: Success (Returned titles, snippets, and official python.org URLs in 0.32s)

# 2. End-to-End Sub-Agent Worker Test (Grace Hopper):
Task: "Search the web for Astro 5.0 release and summarize its top 2 new features"
Output:
> ⚙️ Worker calling tool: web_search...
* Astro Content Layer: Robust, type-safe API with 5x faster builds.
* Server Islands: Effortlessly combine static pages with deferred server rendering.
```
