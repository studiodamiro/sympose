---
name: "subagent_spawn"
title: "Sub-Agent Worker Spawning & Ephemeral Delegation"
description: "Protocol for parent agents to dispatch isolated, skill-equipped sub-agent workers and synthesize beautified, high-signal execution reports without polluting active context."
recommended_models:
  - "gemini/gemini-3.5-flash-lite"
  - "anthropic/claude-3-5-sonnet-20241022"
  - "openrouter/anthropic/claude-3.5-sonnet"
tags:
  - orchestration
  - sub-agent
  - delegation
  - workers
  - mcp
---

# 🤖 Sub-Agent Worker Spawning & Delegation Protocol

> **The Zero-Pollution Orchestration Law:**  
> **Parent agents must never pollute their primary conversational context with verbose, multi-turn tool calling and raw search payloads.** Delegate intensive research, deep codebase scans, and MCP tool execution to isolated, ephemeral sub-agent workers.

---

## 1. When to Spawn a Sub-Agent Worker

Spawn an ephemeral sub-agent worker when a task requires:
1. **Multi-Turn Tool Execution**: Running multiple commands, web searches, or filesystem modifications.
2. **Specialized Skill Mounting**: Applying specific playbooks (e.g. `code_review`, `system_architecture`, `web_search`) without bloat.
3. **MCP Tool Access**: Utilizing external tools from configured MCP servers (`shell`, `git`, `database`).
4. **Context Isolation**: Complex calculations or scraping that would consume thousands of tokens in main memory.

---

## 2. Autonomic Spawning Syntax (`[SPAWN_WORKER]`)

To dispatch an ephemeral sub-agent worker, emit the `[SPAWN_WORKER]` action tag inline:

```text
[SPAWN_WORKER: <skill_1, skill_2, mcp_server> | <precise task prompt with constraints>]
```

### Examples:
- **Architecture Analysis with Shell MCP**:
  ```text
  [SPAWN_WORKER: system_architecture, shell | Inspect sympose/engine.py and report on stream buffer efficiency.]
  ```
- **Live Web Research**:
  ```text
  [SPAWN_WORKER: web_search | Search the web for recent Python 3.13 free-threading benchmarks.]
  ```

---

## 3. Sub-Agent Execution & Adaptive Deliverables

Sub-agents must dynamically tailor their output format to the specific task objective:
- **For File / Note Retrieval**: Return the exact source metadata and verbatim content cleanly. Do NOT force artificial "Historical Timeline" or "Architecture Decisions" headings.
- **For Code / Architecture Review**: Output the specific code diffs, latency bottlenecks, and concrete refactoring steps.
- **For Live Search / Data**: Output clean tables, facts, and citations without filler commentary.

---

## 4. Parent Agent Synthesis Protocol

Upon receiving the sub-agent worker report:
1. **Zero Raw Re-dumping**: Do not repeat the worker's intermediate raw tool calls verbatim.
2. **Direct Answer Synthesis**: Extract the concrete conclusion, answer the user's primary prompt immediately, and cite the worker's key findings.
3. **Actionable Recommendations**: Provide the next engineering steps based on the worker's output.
