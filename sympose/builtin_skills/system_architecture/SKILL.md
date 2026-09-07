---
name: "system_architecture"
title: "Low-Latency & Clean Systems Architecture"
description: "Guidelines for decoupled, low-latency, maintainable systems."
tags:
  - architecture
  - systems
  - performance
---

# System Architecture Guidelines

When designing, decomposing, or refactoring components:

**Decoupling** — one reason to change per module (SRP). High-level orchestrators
depend on stable interfaces, not concrete implementations. Typed dataclasses and
schemas over untyped state bags.

**Latency & resources** — minimise pre-turn I/O for sub-second TTFT: in-memory
indices, pre-cached descriptors, lazy imports for heavy modules. Bound
conversation history and logs to predictable caps — never unbounded context.
Heavy work (memory extraction, summarisation) runs async/background.

**Fault isolation** — sub-tasks and MCP servers run in isolated child processes
with strict timeouts. If a provider or tool is offline, the primary system keeps
working with clear diagnostics.
