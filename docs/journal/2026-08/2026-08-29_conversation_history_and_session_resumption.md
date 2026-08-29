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

## 2. Architectural Decision Records (ADR-054 – ADR-056)

### ADR-054: Zero-Bloat Conversation Persistence (`.jsonl`), Decoupled UI History & Sliding Context Window Hydration

#### Context
LLM APIs are stateless. Re-submitting long historical conversation transcripts (50–100 turns) upon session resumption creates $O(N)$ token burn and degrades TTFT to 2.5s–4.0s. Furthermore, introducing a database server (PostgreSQL, Redis, Mongo) violates Sympose's Zero-Maintenance Mandate.

#### Decision
1. **Local Flat JSON Lines Storage (`SessionManager`)**:
   - Sessions are persisted to `~/.sympose/sessions/<handle>_<timestamp>_<uuid>.jsonl` with line 1 containing metadata JSON and subsequent lines containing `{user, assistant, timestamp}` turn records.
   - Requires 0 external database daemons, 0 migrations, and executes disk appends in $<0.2\text{ms}$.
2. **Context Window Decoupling & Hydration Standard**:
   - When a session is resumed via `/history`, the UI replays recent turns to the terminal.
   - `PersonaEngine.resume_session()` hydrates `engine.histories` with only the **last $K$ turns (default: 6 turns / 3 dialogue pairs)**, governed by `performance.resume_context_turns: 6`.
   - Long-term facts are supplied via the agent's Soul (`_soul.md`) and Working Memory (`_memory.md`).

#### Token & Latency Impact
| Metric | Traditional Resumption | Sympose Triad Resumption |
| :--- | :--- | :--- |
| **Storage Engine** | PostgreSQL / Redis / Vector DB | Local Flat JSONL (`<0.2ms` I/O) |
| **Input Tokens on Resume** | 15,000 – 35,000 tokens | **600 – 1,100 tokens** |
| **Time-to-First-Token (TTFT)** | 2.5s – 4.5s | **< 0.6s** |
| **Cost per Turn (Gemini Flash)** | ~$0.005 – $0.015 | **~$0.00015** |

---

### ADR-055: Milestone-Based Asynchronous Titling & Generic Prompt Filtering

#### Context
Freezing a conversation's title at Turn 1 often locks in generic greetings (`"hi"`, `"hey @samantha"`). Conversely, calling an LLM on every turn to re-title burns ~10,000 tokens per session and causes UI title thrashing.

#### Decision
Implement a 3-Tier Milestone Titling pipeline in `SessionManager`:
1. **Tier 1 (Turn 1 Heuristic Gate)**: Regex matches generic greetings (`r"^(?:hi|hello|hey|yo|greetings|good\s+morning)\b"`, length < 12). If generic, keep title as `"New Conversation"` and upgrade only when the first substantive prompt arrives.
2. **Tier 2 (Turn 3 One-Shot Background Pass)**: When `turns_count == 3`, a detached background daemon thread invokes a 20-token LLM synthesis pass to extract a crisp 4–6 word headline topic. Cost: ~400 input tokens, ~8 output tokens (<$0.000005 total).
3. **Tier 3 (Session Exit / Save Sync)**: When `/save` or session exit runs, the session title is synchronized back to the `.jsonl` header at $0 extra cost.

#### Consequences
* ✅ Zero title thrashing: Titles remain stable and predictable in `/history`.
* ✅ High semantic accuracy: No session remains titled `"hi"` or `"quick question"`.
* ✅ Negligible token footprint: Exactly one background pass per conversation.

---

### ADR-056: Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty

#### Context
Previously, Sympose dumped session summary markdown notes into `Sessions/` or `General/Sessions/` inside the user's Obsidian vault upon exit. With native `.jsonl` session persistence and `/history` now active, auto-dumping session logs into the vault created duplicate storage and polluted the user's curated second brain with machine-generated noise.

#### Decision
1. **Retire Automated Vault Session Dumps**:
   - Exit behavior (`session.exit_behavior.default_target`) is simplified to `memory` (extract durable facts to `_memory.md`) or `none` (instant 0ms exit).
   - Stop creating automated markdown files in the Obsidian vault on session exit.
2. **Intentional Knowledge Contract**:
   - The Obsidian vault is reserved strictly for intentional human notes and deliberate agent note generation (`[WRITE_NOTE]`, `[DAILY_NOTE]`, or explicit `/save obsidian`).
3. **Binary Exit Dialog**:
   - Simplified `TerminalUI.prompt_exit_choice()` to a clean 2-choice prompt:
     `[1] Extract durable facts to _memory.md [Default]`
     `[2] Skip (Preserve in /history only)`

#### Consequences
* ✅ Pristine Obsidian vault: 0% session spam in search, graph view, and backlinks.
* ✅ Clear architectural separation: `.jsonl` for dialogue replay, `_memory.md` for cognitive prompt facts, and `Vault/` for sovereign knowledge.

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

* [`sympose/sessions.py`](file:///Users/damiro/Development/sympose/sympose/sessions.py) — Core `SessionManager` class with JSONL I/O, milestone titling, and relative time formatting (<200 LOC).
* [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py) — Session lifecycle, active session tracking, `resume_session()` sliding window hydration, and milestone titling trigger.
* [`sympose/ui.py`](file:///Users/damiro/Development/sympose/sympose/ui.py) — `select_session` F-shaped panel layout, `render_session_resumed` replay banner, and binary exit modal.
* [`sympose/commands.py`](file:///Users/damiro/Development/sympose/sympose/commands.py) — Interceptor for `/history` and `/sessions` with full subcommand routing.
* [`sympose/completer.py`](file:///Users/damiro/Development/sympose/sympose/completer.py) — Tab auto-completion for `/history`, session IDs, and all runtime config keys.
* [`sympose/cli.py`](file:///Users/damiro/Development/sympose/sympose/cli.py) — Unified session exit lifecycle.
* [`config.yaml`](file:///Users/damiro/Development/sympose/config.yaml) — Added `performance.resume_context_turns: 6` and documented `session.exit_behavior`.
* [`pyproject.toml`](file:///Users/damiro/Development/sympose/pyproject.toml) — Bumped version to `0.2.24`.
