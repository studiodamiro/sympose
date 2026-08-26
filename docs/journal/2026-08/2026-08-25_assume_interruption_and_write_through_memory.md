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

## ADR-029: Assume Interruption Meta-Directive & Write-Through State Checkpointing

### Context & Problem Statement
1. **Bounded Sliding Window Latency SLA**: Sympose enforces a strict 15-turn sliding context window (`performance.max_context_turns: 15`) to guarantee sub-0.8s TTFT.
2. **Context Eviction Risk**: Long discussions on complex refactors risk having early architectural decisions evicted from active context.
3. **Cross-Client Session Resets**: Users switch between local terminal CLI (`./chat.sh`), IDE agents, and Slack mobile Socket Mode. Unpersisted conversational context does not follow the user across channels.

### The Injected Directive
```text
"ASSUME INTERRUPTION: Your context window is bounded and might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory. Proactively checkpoint architectural decisions, milestone progress, and user facts using [REMEMBER: <fact>] or [WRITE_NOTE: <filename> | <content>]."
```

### Architectural Decisions & Consequences

1. **Survival Pressure & Proactive Checkpointing**:
   - Rather than waiting for an explicit `/save` or session termination, models immediately emit autonomic action tags (`[REMEMBER]`, `[WRITE_NOTE]`) when key milestones or architectural decisions are reached.
   - Progress is committed directly to disk before executing subsequent steps.

2. **Zero-Friction Crash & Truncation Recovery**:
   - If a session terminates unexpectedly, the next session instantly recovers full state by reading the agent's memory files on turn 1.

3. **Asynchronous Cross-Channel State Parity**:
   - Work started in the terminal or VS Code is immediately available to mobile Slack DMs because facts are written directly to `profiles/*_memory.md` and shared team pools.

4. **Preserved Modularity & Token Budget**:
   - Added zero runtime latency or external dependencies.
   - Seamlessly integrates with the non-blocking background `MemoryCompactor` daemon.

---

## Verification & Test Results
- Verified prompt assembly via `ProfileManager.build_system_prompt()` across all personas (`@grace`, `@samantha`, `@aurelius`).
- Verified that all Python modules pass syntax and compile checks (`python3 -m py_compile sympose/profiles.py`).
