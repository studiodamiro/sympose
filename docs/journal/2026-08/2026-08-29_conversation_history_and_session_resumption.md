---
entry: 2026-08-29
created: 2026-08-29 19:05
type: journal
project: sympose
tags:
  - conversation-history
  - session-resumption
  - jsonl-storage
  - milestone-titling
  - memory-architecture
  - adr
---

# 2026-08-29: Conversation History Persistence (`/history`), Milestone Smart Titling & Zero-Pollution Memory Sovereignty (ADR-054 – ADR-056)

> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Milestones:** Zero-Bloat JSONL Session Persistence (`~/.sympose/sessions/`), Sliding Context Window Hydration (`performance.resume_context_turns: 6`), F-Shaped History UI Modal (`/history` & `/history all`), Milestone-Based Smart Titling ($0 to <$0.000005 cost), and Retirement of Automated Vault Session Dumping.

---

## 1. Executive Summary & Problem Statement

To provide full conversational continuity across terminal restarts without compromising Sympose's core mantra—**sub-second latency (`<0.8s TTFT`), zero background infrastructure daemons, and cheap token usage**—three interrelated architectural decisions were designed, implemented, verified, and shipped:

1. **Decoupled UI History vs. LLM Context Window**:
   - Traditional AI interfaces re-send full transcripts (10,000–35,000 tokens) on resumption, creating severe TTFT latency degradation and token explosion.
   - Sympose decouples verbatim UI replay (stored locally in `<0.2ms` JSON Lines files) from active LLM context hydration (capped to the last 6 turns / 3 dialogue pairs), relying on the agent's pre-compacted **Working Memory (`_memory.md`)** to retain durable long-term facts.
2. **Interactive History Command Suite (`/history`)**:
   - Implemented `/history` (scoped to active agent), `/history all` (cross-agent global timeline), `/history new`, `/history resume <id>`, `/history view <id>`, and `/history delete <id>` with full Tab auto-completion.
   - Built a high-signal, F-shaped Rich modal presentation putting conversation topic headlines at eye-level with indented secondary metadata.
3. **Milestone-Based Smart Titling System**:
   - Solved the dilemma of static Turn 1 title obsolescence versus high-cost per-turn LLM re-titling by implementing a 3-tier milestone approach: Turn 1 greeting filtering ($0), Turn 3 one-shot background synthesis (<$0.000005), and exit/save sync ($0).
4. **Retirement of Automated Vault Session Dumping (Zero Vault Pollution)**:
   - Eliminated automated markdown note dumps into `Sessions/` inside the user's Obsidian vault. Chat transcripts live in sovereign `.jsonl` files; the user's Obsidian vault remains 100% pristine for human-curated notes and intentional agent documentation.

---

## 2. Architectural Decision Records

- **[ADR-054 - Zero-Bloat Conversation Persistence (`.jsonl`), Decoupled UI History & Sliding Context Window Hydration](./2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md):**
  local flat JSONL sessions (`< 0.2 ms` appends, no DB) with resume hydration
  capped to the last 6 turns (`performance.resume_context_turns`) - ~600-1,100
  tokens and `< 0.6 s` TTFT versus 15k-35k tokens for full-transcript resume.
- **[ADR-055 - Milestone-Based Asynchronous Titling & Generic Prompt Filtering](./2026-08-29_adr-055-milestone-based-async-titling.md):**
  a 3-tier pipeline - turn-1 greeting gate, turn-3 one-shot background synthesis
  (`< $0.000005`), exit/save sync - rejecting both a frozen turn-1 title and
  per-turn LLM re-titling.
- **[ADR-056 - Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty](./2026-08-29_adr-056-retire-automated-vault-session-dumping.md):**
  stop dumping `Sessions/` Markdown into the vault; exit collapses to
  `memory` / `none`; a binary exit dialog. **Supersedes** the session-log dump
  from [ADR-005](./2026-08-24_adr-005-config-yaml-session-summarization-memory.md).

---

## 3. Verification & Test Evidence

### Test Suite (`scratch/test_history_sessions.py`)
```bash
python3 scratch/test_history_sessions.py
```
* **Results**:
  * `test_session_manager_lifecycle`: Passed. Verified session creation, turn appending, JSONL formatting, listing by handle vs global, and deletion.
  * `test_engine_resume_and_hydration`: Passed. Verified that resuming a 10-turn session hydrates active history with exactly 6 turns (12 messages).
  * `test_command_interceptor_history`: Passed. Verified `/history new`, `/history delete <id>`, `/history resume <id>`, and `/history view`.
  * `test_completer_integration`: Passed. Verified tab completion for all `/history` subcommands, session IDs, and runtime config keys.
  * `test_milestone_titling`: Passed. Verified Turn 1 greeting filtering and substantive title upgrades.
* **Execution Time**: 0.016s across 5 test suites.

---

## 4. Modified Files Reference

* [`sympose/sessions.py`](../../../sympose/sessions.py) — Core `SessionManager` class with JSONL I/O, milestone titling, and relative time formatting (<200 LOC).
* [`sympose/engine.py`](../../../sympose/engine.py) — Session lifecycle, active session tracking, `resume_session()` sliding window hydration, and milestone titling trigger.
* [`sympose/ui.py`](../../../sympose/ui.py) — `select_session` F-shaped panel layout, `render_session_resumed` replay banner, and binary exit modal.
* [`sympose/commands.py`](../../../sympose/commands.py) — Interceptor for `/history` and `/sessions` with full subcommand routing.
* [`sympose/completer.py`](../../../sympose/completer.py) — Tab auto-completion for `/history`, session IDs, and all runtime config keys.
* [`sympose/cli.py`](../../../sympose/cli.py) — Unified session exit lifecycle.
* [`config.yaml`](../../../config.yaml) — Added `performance.resume_context_turns: 6` and documented `session.exit_behavior`.
* [`pyproject.toml`](../../../pyproject.toml) — Bumped version to `0.2.24`.
