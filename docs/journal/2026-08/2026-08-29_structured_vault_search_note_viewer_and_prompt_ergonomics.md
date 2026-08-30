---
entry: 2026-08-29
created: 2026-08-29 20:18
type: journal
project: sympose
tags:
  - vault-search
  - multi-section-panel
  - t-junction-boxes
  - frontmatter-parser
  - interactive-browser
  - signal-interruption
  - prompt-ergonomics
  - adr
---

# 2026-08-29: Orderly Structured Vault Search (`/vault`), Inline T-Junction Note Viewer, Signal Interruption (`SIGINT`) & Systematic Prompt Ergonomics (ADR-057 – ADR-059)

> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Milestones:** Orderly Structured Vault Search with Single-Line Excerpts, In-Terminal Boxed Note Reader (`/read`, `/view`), Inline T-Junction Section Dividers (`MultiSectionPanel`), Repository-Wide Clean Range Prompts, and Graceful Asynchronous `Ctrl+C` Interruption.

---

## 1. Executive Summary & Problem Statement

This engineering cycle resolved four major usability and design issues across Sympose's terminal interface and knowledge retrieval subsystem:

1. **Vault Search Chaos & High-Volume Output Dumps**:
   - *Problem:* Searching `/vault "query"` dumped raw 1,200-character unstructured file heads into the terminal. In large vaults with 15+ matches, this produced a chaotic wall of text that was difficult to parse.
   - *Solution:* Replaced raw dumps with structured, two-line search listings featuring numerical badges `[1-N]`, match classifications (`Title Match` vs. `Line N`), YAML `#tags` chips, and normalized single-line context excerpts capped at 70 characters with trailing ellipsis (`...`).

2. **Terminal-Native Note Reading with Inline T-Junction Borders**:
   - *Problem:* Users had to leave the terminal and open external GUI apps just to read a matching note. Furthermore, preliminary Rich implementations used detached floating horizontal rules that failed to connect to outer panel walls.
   - *Solution:* Built `MultiSectionPanel`, a custom Rich renderable that draws single-frame boxes with inline section titles in the top border (`╭─ 📄 NOTE: ... ─╮`) and rotated T-junction dividers (`├─ 🏷️ FRONTMATTER ─┤` and `├──────┤`) that physically meet the left and right borders.

3. **Prompt Choice Bloat & Choice List Dumping**:
   - *Problem:* When `choices=` was passed to Rich's `Prompt.ask`, Rich automatically dumped every possible string (including full timestamped session IDs) in square brackets:
     `[1/samantha_20260829_200809_366347/2/samantha_20260829_200153_80319f/.../q/cancel/exit/] (1):`
   - *Solution:* Conducted a systematic audit of all `Prompt.ask` calls across `sympose/ui.py`, `sympose/cli.py`, and `sympose/bootstrap.py`. Enforced `show_choices=False, show_default=False` and implemented clean range prompts (`Select note [1-11, 'o <#>' to open, 'q' to exit]:`).

4. **Unhandled `Ctrl+C` Application Crash**:
   - *Problem:* Pressing `Ctrl+C` (`SIGINT`) during agent thinking or token streaming caused an uncaught `KeyboardInterrupt` that escaped the loop and killed the entire Sympose process.
   - *Solution:* Trapped `KeyboardInterrupt` across all three interaction layers (prompt input, slash commands, and LLM streaming), enabling instant turn interruption (`^C [Interrupted @persona]`) while keeping the session alive.

---

## 2. Architectural Decision Records (ADR-057 – ADR-059)

### ADR-057: Orderly Structured Vault Retrieval & Single-Line Context Excerpts

#### Context
Prior to ADR-057, `VaultManager.search()` concatenated up to 1,200 characters of raw Markdown text from matching files into a single long string. When multi-folder whitelists matched multiple documents, the user received an overwhelming dump of text.

#### Decision
1. **`VaultManager.parse_frontmatter(content)`**:
   - Uses regex to parse YAML metadata blocks (`--- ... ---`) at the head of notes into a typed `dict` (`title`, `tags`, `author`, `created`, `aliases`), returning clean markdown bodies separated from metadata.
2. **Structured Search Engine (`search_structured`)**:
   - Traverses whitelisted folders in `<10ms` and returns structured dictionaries:
     ```python
     {
         "file_name": "Architecture.md",
         "rel_path": "Projects/Architecture.md",
         "abs_path": "/Users/damiro/Obsidian/Vault/Projects/Architecture.md",
         "match_type": "title" | "content",
         "line_no": 15,
         "snippet": "Core specifications and authentication flow directives...",
         "title": "System Architecture Spec",
         "tags": ["architecture", "auth", "security"],
         "meta": {...}
     }
     ```
3. **Dedicated Indented `#tags` Line & Single-Line Excerpt Normalization**:
   - Note header line contains the numerical badge `[N]` and filename `(Line #)` without crowded trailing text.
   - Frontmatter `#tags` are placed on their own indented line (`    #tag1 #tag2 #tag3`) to prevent wrapping long note paths.
   - All internal whitespace and newlines in excerpts are flattened (`" ".join(snippet.split())`) and strictly capped at 70 characters with ellipsis (`...`), ensuring clean and predictable 2–3 line cards.
4. **Session Cache & Index Resolution**:
   - Caches the last search in `VaultManager._last_searches[profile_handle]` so users can reference notes by simple numerical indexes `1-N`.

---

### ADR-058: `MultiSectionPanel` In-Terminal Note Viewer with Inline T-Junction Box Dividers

#### Context
Standard Rich `Panel(Group(header, Rule(), fm, Rule(), body))` places horizontal rules inside the panel's interior padding, producing detached lines that do not meet the outer border. The user requested pixel-perfect box-drawing borders with rotated T-junctions (`├` / `┤`) where section titles are embedded inline with the border lines.

#### Decision
1. **Custom `MultiSectionPanel` Renderable**:
   - Implemented a native Rich renderable utilizing `Segment` streaming and `options.max_width`:
     - **Top Border**: `╭─ 📄  NOTE: <rel_path> ────────╮`
     - **Inner Section 1**: High-density metadata stats (`Path`, `Lines`, `Size`).
     - **Section Divider**: `├─ 🏷️  FRONTMATTER ────────┤`
     - **Inner Section 2**: Colorized YAML frontmatter tags chips, authors, and dates.
     - **Body Divider**: `├──────────────────────────┤`
     - **Inner Section 3**: Syntax-highlighted Markdown note body.
     - **Bottom Border**: `╰──────────────────────────╯`
2. **Interactive Quick-Nav Loop (`interactive_vault_browser`)**:
   - Allows users to jump between notes by typing numbers `1-N`, open notes in Obsidian (`o`), return to list (`b`), or exit (`q`) without re-running search commands.

#### Visual Output Specification

```
╭─ 📄  NOTE: Projects/Architecture.md ─────────────────────────────────────────╮
│                                                                              │
│  Path: Projects/Architecture.md  •  Lines: 48  •  Size: 1.8 KB               │
│                                                                              │
├─ 🏷️  FRONTMATTER ────────────────────────────────────────────────────────────┤
│                                                                              │
│  Title: System Architecture Spec                                             │
│  Tags: #architecture #auth #security                                         │
│  Author: Grace                                                               │
│  Created: 2026-08-25                                                         │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  # Architecture Overview                                                     │
│                                                                              │
│  Core specifications and authentication flow directives...                   │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

### ADR-059: Repository-Wide Clean Range Prompts & Graceful Asynchronous Signal Interruption (`SIGINT` / `Ctrl+C`)

#### Context
Two critical terminal usability flaws were identified:
1. Rich's default `Prompt.ask` behavior outputs all members of `choices` in the prompt string. For session selection, this printed all 30-character session IDs in the prompt line.
2. Pressing `Ctrl+C` while an agent was thinking or streaming raised an unhandled `KeyboardInterrupt`, crashing the process and losing session continuity.

#### Decision
1. **Clean Range Prompts**:
   - Set `show_choices=False, show_default=False` on all `Prompt.ask` invocations across `sympose/ui.py` and `sympose/bootstrap.py`.
   - Replaced verbose choice dumps with clean, human-readable range indicators:
     - Session Selection: `Select session to resume [1-5, Enter for [1], 'q' to cancel]:`
     - Persona Selection: `Select persona [1-3 or @handle, Enter for default]:`
     - Memory Exit: `Select option [1-2, Enter for [1]]:`
     - Vault Browser: `Select note [1-11, 'o <#>' to open, 'q' to exit]:`
2. **Three-Tier Graceful Signal Trapping (`sympose/cli.py`)**:
   - **Generation Tier**: Traps `KeyboardInterrupt` in `chat_stream()`, halts token streaming and spinner, prints `^C [Interrupted @handle]`, and returns immediately to the input prompt.
   - **Command Tier**: Traps `KeyboardInterrupt` during slash command execution and prints `^C [Command cancelled]`.
   - **Prompt Tier**: Traps `KeyboardInterrupt` on the input line, prints `(Type /exit or press Ctrl+D to quit)`, and stays in the REPL session.

---

### ADR-060: Terminal Markdown Presentation Standard (`vault_recall`) & Beautified Sub-Agent Orchestration (`subagent_spawn`)

#### Context
1. Agents lacked codified guidance on how to format recalled Markdown notes and citations inside the terminal, leading to inconsistent quote styles.
2. Sub-agent worker execution badges and live web search summaries were formatted as raw single-line quotes without visual hierarchy.

#### Decision
1. **Codified Terminal Markdown Standard in `vault_recall` (`skills/vault_recall/SKILL.md`)**:
   - Injected Section 4 into the `vault_recall` playbook establishing the 3-tier box anatomy: Header Metadata bar, Frontmatter metadata `#tags`, and syntax-highlighted clean Markdown body with rotated T-junction section dividers.
2. **Dedicated Sub-Agent Spawning Skill (`skills/subagent_spawn/SKILL.md`)**:
   - Created `subagent_spawn` skill defining the zero-pollution orchestration law, `[SPAWN_WORKER]` action tag syntax, skill/MCP mounting rules, and parent synthesis directives.
3. **Beautified Worker & Search Reports (`sympose/actions.py`)**:
   - Upgraded `SPAWN_WORKER` and `WEB_SEARCH` output generation to emit styled blockquotes featuring Markdown headers (`### 🛠️ Sub-Agent Worker Report`), skill capability chips (`[Skills: ...]`), and structured task metadata.

---

### ADR-061: Intelligent Ghost Session Pruning & Substantive Conversation Gating

#### Context
Whenever a user launched the Sympose CLI and typed ephemeral single-word commands (like `history`, `3`, `q`, or simple greetings), Sympose wrote a persistent JSONL session file. This cluttered `/history` with trivial 1-turn `"New Conversation"` ghost sessions without substantive context.

#### Decision
1. **Automated Ghost Session Pruning (`SessionManager.prune_ghost_sessions`)**:
   - Scans `sessions/*.jsonl` on listing, persona switching, and session resets.
   - Automatically deletes 0-turn empty sessions and 1-turn generic greeting sessions (`turns_count <= 1` with generic titles `"New Conversation"` / `"Untitled Session"`).
   - Preserves currently active sessions in memory while preventing persistent disk bloat.
2. **Substantive History Listing**:
   - `/history` now filters out trivial ghost artifacts, ensuring the historical session list contains strictly meaningful, multi-turn, and topic-anchored discussions.

---

### ADR-062: Sub-Agent Worker Report Panel Styling & Redundant Synthesis Gating

#### Context
1. Sub-agent worker tool outputs were formatted as nested blockquotes (`> > ⚙️ Worker calling tool:`), causing Rich markdown wrapping issues and stripping color hierarchy.
2. Actions executed by workers were incorrectly attributed to the parent agent (`Samantha rendered note`).
3. After a worker successfully rendered a note in the terminal, the parent agent executed an unnecessary, expensive 2nd LLM round (`synth_resp`) attempting to re-synthesize and dump the full note text again, adding 30+ seconds of latency and token waste.

#### Decision
1. **Styled Sub-Agent Worker Report Panel (`TerminalUI.render_worker_report_panel`)**:
   - Renders a dedicated yellow-bordered Rich panel (`╭─ 🛠️ SUB-AGENT WORKER REPORT • #skills ─╮`) displaying executed tool calls (`⚙️ Tool: read_file(...)`) and syntax-highlighted deliverables.
2. **Worker Actor Attribution**:
   - Actions executed by sub-agents are properly attributed to `"Sub-Agent Worker"` (`> 📄 Sub-Agent Worker rendered note to Terminal:`).
3. **Redundant Synthesis Turn Gating (`sympose/engine.py`)**:
   - If a worker has already rendered the note to the terminal (`has_rendered_note`), the parent engine skips the redundant 2nd LLM completion round, delivering instant sub-second turnaround and saving thousands of tokens.

---

### ADR-063: Live Stream Markdown Parsing for Real-Time Badges & Sub-Agent Reports

#### Context
While replaying history (`/history`) rendered Markdown turns through `TerminalUI.render_markdown()` with proper `▌` vertical bars and ANSI syntax styling, live chat streaming wrote raw badge and report strings directly to `sys.stdout.write()`. This caused live sub-agent reports to output raw markdown characters (`> `, `**`, `###`) rather than formatted Rich Markdown.

#### Decision
1. **Live Stream Badge Interception (`sympose/cli.py`)**:
   - In the live token streaming consumer, chunks containing badge and report payloads (`chunk.startswith("\n\n>") or "\n> " in chunk`) are automatically parsed and rendered with `TerminalUI.render_markdown(self.console, chunk.strip())`.
2. **Unified Visual Fidelity**:
   - Live real-time sub-agent execution reports now render with the exact same visual quality (purple `▌` bars, italicized task metadata, and clean tool call chips) as the `/history` replayer.

---

## 3. Implementation Summary & Verification

### Modified Components
- [`sympose/cli.py`](../../../sympose/cli.py): Live stream markdown parsing for badge and worker report chunks.
- [`sympose/ui.py`](../../../sympose/ui.py): `MultiSectionPanel`, `render_worker_report_panel`, frontmatter key filter.
- [`sympose/workers.py`](../../../sympose/workers.py): `execute_worker_task` with structured tool call tracking.
- [`sympose/actions.py`](../../../sympose/actions.py): Worker actor attribution and worker report formatting.
- [`sympose/engine.py`](../../../sympose/engine.py): Redundant synthesis gating for note reads.
- [`sympose/sessions.py`](../../../sympose/sessions.py): Ghost session pruning and substantive history filtering.
- [`sympose/vault.py`](../../../sympose/vault.py): Frontmatter parser, structured search, index caching.
- [`skills/vault_recall/SKILL.md`](../../../skills/vault_recall/SKILL.md) & [`skills/subagent_spawn/SKILL.md`](../../../skills/subagent_spawn/SKILL.md): Adaptive deliverable playbooks.

### Verification Results
- Verified live stream badge rendering in `scratch/test_live_rendering.py` with zero syntax errors.
- Verified `MultiSectionPanel` note reader and yellow `render_worker_report_panel` execution in integration tests.
- All Python modules compiled cleanly with zero syntax errors.
