---
name: "system_architecture"
title: "Low-Latency & Clean Systems Architecture"
description: "Architectural guidelines for building decoupled, low-latency, and maintainable systems."
tags:
  - architecture
  - systems
  - performance
---

# 🏛️ System Architecture Guidelines

When designing, decomposing, or refactoring system components, adhere to these fundamental principles:

## 1. Decoupling & Interface Segregation
- **Single Responsibility Principle**: Each module should have one reason to change and encapsulate a single coherent responsibility.
- **Dependency Inversion**: High-level orchestrators should depend on stable interfaces, not fragile concrete implementations.
- **Explicit Contracts**: Prefer typed dataclasses, schemas, or typed dictionaries over arbitrary, untyped state bags.

## 2. Latency & Resource Efficiency
- **Sub-Second TTFT (Time-to-First-Token)**: Minimize pre-turn I/O. Use local in-memory indices, pre-cached descriptors, and lazy imports for heavy modules.
- **Sliding Windows**: Never accumulate unbound memory contexts. Bound conversation history and session logs to predictable memory caps.
- **Non-Blocking Execution**: Asynchronous or background tasks for heavy operations (e.g. background memory extraction, summarization).

## 3. Sandboxing & Fault Isolation
- **Blast-Radius Containment**: Sub-tasks and external integrations (like MCP servers) should run in isolated child processes with strict timeouts.
- **Graceful Degradation**: If an external provider or tool is offline, the primary system must continue functioning with clear diagnostic feedback.
