---
name: "subagent_spawn"
title: "Sub-Agent Spawning & Delegation"
description: "Dispatching isolated, skill-equipped sub-agents via [SPAWN_SUB_AGENT] and synthesising their reports without polluting the main context."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "anthropic/claude-3-5-sonnet-20241022"
tags:
  - orchestration
  - sub-agent
  - delegation
---

# Sub-Agent Spawning & Delegation

Delegate intensive work to an ephemeral sub-agent instead of running many tool calls
in your own context. (Never fake a sub-agent report — see Universal Workspace Rules.)

## When to spawn

- Multi-turn tool execution (several commands, searches, or file edits).
- Applying a heavy skill playbook in isolation (`code_review`, `system_architecture`).
- MCP tool access (`shell`, `git`, `database`).
- Work that would otherwise burn thousands of tokens of intermediate output.

Do **not** spawn if the answer is already in your pre-turn context — answer
in-turn.

## Syntax

```
[SPAWN_SUB_AGENT: <skill_1, skill_2, mcp_server> | <precise task with constraints>]
```

Examples:
```
[SPAWN_SUB_AGENT: system_architecture, shell | Inspect sympose/engine.py and report on stream-buffer efficiency.]
[SPAWN_SUB_AGENT: web_search | Current AXS token price in USD, 24h volume, recent developments.]
```

## Synthesising the report

1. Don't re-dump the sub-agent's raw tool calls.
2. Extract the concrete conclusion, answer the user's question immediately, cite
   the key findings.
3. Give the next actionable steps.
