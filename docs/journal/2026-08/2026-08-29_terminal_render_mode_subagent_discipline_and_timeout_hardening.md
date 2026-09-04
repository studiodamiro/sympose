---
entry: 2026-08-29
created: 2026-08-29 22:21
type: journal
project: sympose
tags:
  - render-mode
  - render-knob
  - sub-agent-discipline
  - read-note-gate
  - timeout-hardening
  - compactor
  - memory-compaction
  - slash-commands
  - autocomplete
  - adr
---

# 2026-08-29: Terminal Render Mode Knob, Sub-Agent `[READ_NOTE]` Discipline & System-Wide Timeout Hardening (ADR-060 – ADR-063)

> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Milestones:** Three-way terminal render mode toggle (`/render`), sub-agent `[READ_NOTE]` explicit-intent gating, system-wide LLM timeout audit & hardening, and `_shared_memory.md` manual compaction.

---

## 1. Executive Summary & Problem Statement

This engineering cycle resolved four compounding issues across Sympose's streaming pipeline, sub-agent orchestration layer, and background LLM call infrastructure:

1. **Terminal Output Rendering Was Binary (No User Control)**:
   - *Problem:* Sympose had no concept of a render mode. All terminal output was either Rich-formatted or raw stdout — with no way for the user to toggle between streaming transparency and full Markdown rendering.
   - *Solution:* Implemented a three-way `performance.render_mode` knob (`hybrid`, `buffered`, `raw`) in `config.yaml`, wired into `cli.py`'s streaming loop, and exposed as an interactive `/render` slash command with a standard cyan box menu.

2. **Sub-Agent Workers Over-Triggered `[READ_NOTE]` on Non-Reading Tasks**:
   - *Problem:* `prompts/worker_system.md` Directive 2 instructed workers: *"When retrieving, finding, or presenting notes from the vault, emit `[READ_NOTE]`."* This caused workers to fire the full terminal note viewer panel even for tasks like "pick a random movie" — resulting in a 27-line full note dump instead of a concise pick summary.
   - *Solution:* Rewrote Directive 2 to explicitly gate `[READ_NOTE]` only for user requests that clearly ask to *read, view, pull up, or open* a full note. For search, query, or random-pick tasks, workers return a concise factual answer directly in text.

3. **`render_mode: raw` Did Not Suppress Rich Box Panels in `READ_NOTE` Actions**:
   - *Problem:* Even with `render_mode: raw` set, executing `[READ_NOTE]` still rendered the full `MultiSectionPanel` Rich viewer, violating the user's intent for pure terminal transparency.
   - *Solution:* In `actions.py`, added `render_mode` detection before `TerminalUI.render_vault_note_panel()` — if `raw`, `console` is passed as `None` to suppress the Rich panel.

4. **System-Wide LLM Timeout Fragility**:
   - *Problem:* Three separate background LLM call sites (`compactor.py`, `memory.py` heuristic extractor, `memory.py` session archivist) had hardcoded timeouts of `10.0s`, `5.0s`, and `10.0s` respectively — all ignoring `config.yaml`. Under network jitter, these caused compaction failures, memory extraction silent drops, and session summary errors.
   - *Solution:* All three sites now read `float(config_manager.get("performance.request_timeout", 30.0))`. The global default was raised from `10.0s` → `30.0s` across `config.yaml`, `config.py`, and `engine.py`.

---

## 2. Architectural Decision Records

- **[ADR-060 - Three-Way Terminal Render Mode Knob (`performance.render_mode`)](./2026-08-29_adr-060-terminal-render-mode-knob.md):**
  `hybrid` / `buffered` / `raw` modes wired through `cli.py`, `ui.py`,
  `commands.py` (`/render`), `completer.py`; also fixes a `first_chunk`
  `UnboundLocalError`.
- **[ADR-061 - Sub-Agent `[READ_NOTE]` Explicit-Intent Gating](./2026-08-29_adr-061-subagent-read-note-explicit-intent-gating.md):**
  `worker_system.md` Directive 2 rewritten - `[READ_NOTE]` only for explicit
  read/view/open/pull-up; concise text for search / pick / Q&A.
- **[ADR-062 - `render_mode: raw` Panel Suppression in the Action Executor](./2026-08-29_adr-062-render-mode-raw-panel-suppression.md):**
  `actions.py` passes `console=None` for `[READ_NOTE]` when
  `render_mode == raw`, suppressing the Rich panel.
- **[ADR-063 - System-Wide LLM Timeout Hardening](./2026-08-29_adr-063-system-wide-llm-timeout-hardening.md):**
  every LLM call site reads `performance.request_timeout` (raised `10 -> 30 s`;
  Ollama `60 -> 120 s`); no hardcoded timeouts.

---

## 3. `/help` & Autocomplete Updates

- **`sympose/commands.py`**: `/render [hybrid|buffered|raw]` added under `### ⚙️  RUNTIME SETTINGS` in `/help` output.
- **`sympose/completer.py`**: `/help <cmd>` now completes available command names as topic arguments.

---

## 4. Manual `_shared_memory.md` Compaction

`profiles/_shared_memory.md` accumulated **65 duplicate entries** after multiple LLM-driven extraction passes ran without compaction (due to the timeout bug). The file was manually distilled to **45 clean, non-redundant bullets** organized into thematic sections:
- System architecture & model tiers
- Obsidian vault (path, sandbox, notable notes)
- User preferences & context
- ADR index
- Workspace channels
- Project assets

The `/compact shared` command subsequently ran successfully after the app restart, confirming the timeout fix was live.

---

## 5. Files Modified

| File | Change |
|---|---|
| `config.yaml` | Added `render_mode: raw`, raised `request_timeout: 30.0` |
| `sympose/cli.py` | Render mode branch logic, fixed `UnboundLocalError` |
| `sympose/ui.py` | `TerminalUI.select_render_mode()` cyan box menu |
| `sympose/commands.py` | `/render` command, `/help` entry added |
| `sympose/completer.py` | `/render` sub-commands, `/help` topic autocomplete |
| `sympose/actions.py` | `render_mode` check in `READ_NOTE`, fix indentation |
| `sympose/config.py` | Raised default `request_timeout` to `30.0` |
| `sympose/engine.py` | `_build_kwargs` fallback to `30.0s` / `120.0s` |
| `sympose/compactor.py` | Read `config_manager.get("performance.request_timeout")` |
| `sympose/memory.py` | Both timeout sites read from config |
| `prompts/worker_system.md` | Directive 2 rewritten: explicit `[READ_NOTE]` gating |
| `profiles/_shared_memory.md` | Manual compaction: 65 → 45 lines, no duplicates |
