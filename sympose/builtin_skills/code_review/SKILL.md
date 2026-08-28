---
name: "code_review"
title: "Zero-Bloat Code Review & Static Heuristics"
description: "Rigorous code review protocol focusing on simplicity, error boundaries, race conditions, and cognitive load."
tags:
  - engineering
  - quality
  - review
---

# 🔍 Zero-Bloat Code Review Protocol

When performing code reviews, apply surgical scrutiny across these four core pillars:

## 1. Simplicity & Bloat Elimination
- **Occam's Razor**: Can this be solved with standard library primitives instead of adding a new dependency?
- **Avoid Speculative Generality (YAGNI)**: Eliminate unnecessary abstractions, factory wrappers, or generic adapter layers that only have a single concrete implementation.
- **Cognitive Load**: Keep function cyclomatic complexity low. Flat is better than nested; early returns are preferred over nested `if/else` ladders.

## 2. Robustness & Error Boundaries
- **Explicit Failure Modes**: Do not catch generic exceptions (`except Exception: pass`) unless specifically intended and logged. Handle specific edge cases.
- **Resource Leaks**: Ensure all file handles, database cursors, and network connections use context managers (`with` blocks) or deterministic cleanup.
- **Input Sanitization**: Validate types and boundaries at system entry points.

## 3. Concurrency & State Integrity
- **Thread Safety**: Look for shared mutable state, unprotected global dictionaries, or un-synchronized counter increments.
- **Idempotency**: Ensure retryable operations (e.g. webhook listeners, payment calls) are safe to execute multiple times without duplicate side effects.

## 4. Review Output Format
Provide review findings in structured, actionable tiers:
1. 🚨 **Blockers (Critical)**: Bugs, security risks, race conditions, data loss.
2. ⚠️ **Warnings (Important)**: Performance bottlenecks, unhandled edge cases, missing test coverage.
3. 💡 **Suggestions (Nitpicks)**: Naming clarity, minor refactoring, style consistency.
