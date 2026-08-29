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

## 2. Architectural Decision Records (ADR-060 – ADR-063)

### ADR-060: Three-Way Terminal Render Mode Knob (`performance.render_mode`)

#### Context
Users have different priorities for terminal output: developers want streaming transparency to see raw token flow in real-time; power users want pixel-perfect Rich Markdown; casual users want a live-streaming hybrid that still renders structured badges correctly.

#### Decision
Three modes, controlled by `config.yaml → performance.render_mode`:

| Mode | Behavior | Use Case |
|---|---|---|
| `hybrid` | Live streaming with Rich badge rendering intercepted mid-stream | Default for daily use |
| `buffered` | Spins during generation, renders full response with Rich Markdown | When visual polish matters |
| `raw` | Pure stdout token streaming, no Rich panels or boxes | Debugging, pipe output, terminal transparency |

#### Implementation
- **`config.yaml`**: Added `render_mode: hybrid` (or `buffered` / `raw`) under `performance:`.
- **`sympose/cli.py`** (lines 173–235): Reads `render_mode` on each turn; branches into `buffered`, `hybrid`, or `raw` execution paths. Fixed `UnboundLocalError: cannot access local variable 'first_chunk'` present before this change.
- **`sympose/ui.py`** (lines 357–415): `TerminalUI.select_render_mode(console, current_mode)` renders the standard cyan `box.ROUNDED` panel with `[1] hybrid`, `[2] buffered`, `[3] raw` options, `[Active]` chip on the current mode, and `Prompt.ask` with `show_choices=False`.
- **`sympose/commands.py`** (lines 217–253): `/render` command wired to `select_render_mode()`. Persists the selected mode back to `config.yaml` via `config_manager.set() + config_manager.save()`. Supports direct arguments: `/render raw`, `/render buffered`, `/render hybrid`.
- **`sympose/completer.py`**: `/render` in `ROOT_COMMANDS`; sub-commands `hybrid`, `buffered`, `raw` in completer dispatch.

#### Consequences
- Single knob in `config.yaml` controls all terminal output behavior.
- `/render` can be called at any time mid-session without restart.
- `/help` now lists `/render` under `### ⚙️  RUNTIME SETTINGS`.

---

### ADR-061: Sub-Agent `[READ_NOTE]` Explicit-Intent Gating

#### Context
`[READ_NOTE]` is an autonomic action tag that triggers the full `MultiSectionPanel` terminal note viewer — a Rich panel with frontmatter parsing, multi-section display, and syntax highlighting. This is appropriate when a user explicitly asks to *see* a note, but is disruptive and wasteful when a worker is merely answering a question or making a random selection from vault files.

#### Decision
`prompts/worker_system.md` Directive 2 was rewritten from:

> *"When retrieving, finding, or presenting notes from the vault, emit `[READ_NOTE: <relative_path>]`"*

to:

> **Emit `[READ_NOTE]` ONLY** when the task explicitly asks to *read, view, pull up, or open* a full note.  
> **For search, query, random-pick, or fact extraction** — return a concise factual answer directly in text. Do NOT emit `[READ_NOTE]`.

#### Implementation
- **`prompts/worker_system.md`**: Directive 2 split into explicit sub-rules with concrete examples (`"pick a random movie"` → no `[READ_NOTE]`; `"pull up Her"` → yes `[READ_NOTE]`).

#### Consequences
- Random picks, searches, and Q&A queries return clean prose answers without flooding the terminal with full documents.
- `[READ_NOTE]` remains fully functional and correctly triggered on explicit user pull-up requests.

---

### ADR-062: `render_mode: raw` Panel Suppression in Action Executor

#### Context
`render_mode: raw` is intended to give the user pure terminal transparency — no Rich formatting, no boxes. However, `[READ_NOTE]` actions in `actions.py` were unconditionally calling `TerminalUI.render_vault_note_panel()` regardless of render mode.

#### Decision
Before rendering any Rich panel for a `[READ_NOTE]` action, `actions.py` reads `config_manager.get("performance.render_mode")`. If `raw`, `console=None` is passed, suppressing the panel. In `hybrid` or `buffered` mode, the full `MultiSectionPanel` renders as intended.

#### Implementation
- **`sympose/actions.py`** (lines 132–138): Added `render_mode` check inside `READ_NOTE` / `VIEW_NOTE` branch.

---

### ADR-063: System-Wide LLM Timeout Hardening

#### Context
Three background LLM calls bypassed `config.yaml` and used stale hardcoded timeout values:
- `compactor.py` → `10.0s` (memory compaction, most expensive LLM call in the system)
- `memory.py:65` (heuristic extractor) → `5.0s` (dangerously aggressive)
- `memory.py:106` (session archivist) → `10.0s` fallback

Under normal network conditions with a cold Gemini connection, the 10.0s ceiling was regularly breached, causing:
- `⚠️ Memory compaction failed: litellm.Timeout: Connection timed out after None seconds`
- Silent memory extraction drops (exception swallowed)

#### Decision
All LLM call sites must read from `config_manager.get("performance.request_timeout", 30.0)`. No site may hardcode a timeout value.

Global default raised from `10.0s` → `30.0s`:

| File | Location | Old Value | New Value |
|---|---|---|---|
| `config.yaml` | `performance.request_timeout` | `10.0` | `30.0` |
| `sympose/config.py` | `litellm.request_timeout` (global) | `10.0` | `30.0` |
| `sympose/config.py` | `DEFAULT_CONFIG["performance"]["request_timeout"]` | `10.0` | `30.0` |
| `sympose/engine.py` | `_build_kwargs` fallback | `10.0` | `30.0` |
| `sympose/compactor.py:85` | Memory compaction call | `10.0` (hardcoded) | `config_manager.get(...)` |
| `sympose/memory.py:65` | Heuristic extractor | `5.0` (hardcoded) | `config.get(...)` |
| `sympose/memory.py:106` | Session archivist | `10.0` fallback | `30.0` fallback |

`local_request_timeout` (Ollama) default raised from `60.0s` → `120.0s` in `engine.py`.

#### Consequences
- All LLM calls respect the single `performance.request_timeout` knob in `config.yaml`.
- Memory compaction, extraction, and session summarization are now resilient to normal network jitter.
- Timeout can be tuned at runtime with `/config set performance.request_timeout 45.0` without restart.

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
