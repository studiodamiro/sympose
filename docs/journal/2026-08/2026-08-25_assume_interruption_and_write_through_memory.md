---
entry: 2026-08-25
created: 2026-08-25 22:15
type: adr-log
project: sympose
tags:
  - adr
  - architecture
  - memory
  - context-window
  - assume-interruption
  - write-through
---

# Architecture Decision Record: "Assume Interruption" & Proactive Write-Through State Memory

> **Date:** 2026-08-25  
> **Author:** damiro & Grace Hopper  
> **Status:** Ratified & Implemented (ADR-029)  
> **Affected Modules:** `sympose/profiles.py`, `profiles/grace_soul.md`, `profiles/samantha_soul.md`, `profiles/aurelius_soul.md`, `.agents/rules/identity.md`

---

## Executive Summary

Standard LLM agent designs suffer from **"Context Complacency"**—models assume conversational history persists indefinitely, allowing intermediate architectural decisions, test results, and user constraints to remain trapped in volatile token buffers. When context windows are truncated, reset via `/clear`, or interrupted across client sessions, state is lost.

This ADR ratifies **ADR-029**, injecting the universal **"ASSUME INTERRUPTION"** meta-directive into Sympose's prompt engine and agent souls, inducing proactive write-through persistence to local memory files (`profiles/*_memory.md`) and Obsidian vault notes.

---

## Architectural Decision Record

- **[ADR-029 — Assume Interruption Meta-Directive & Write-Through State Checkpointing](./2026-08-25_adr-029-assume-interruption-write-through-state.md):**
  a universal "ASSUME INTERRUPTION" directive injected into the prompt engine
  and every soul, driving agents to checkpoint milestones and user facts with
  `[REMEMBER]` / `[WRITE_NOTE]` on reaching them rather than waiting for `/save`
  or exit — so a reset, truncation, or client switch loses nothing.

---

## Verification & Test Results
- Verified prompt assembly via `ProfileManager.build_system_prompt()` across all personas (`@grace`, `@samantha`, `@aurelius`).
- Verified that all Python modules pass syntax and compile checks (`python3 -m py_compile sympose/profiles.py`).
