---
title: "Session Archival & Distillation"
created: 2026-08-24
type: wiki-memory
parent: index
tags:
  - sympose/memory
  - session-archival
  - obsidian-logs
---

# 📑 Session Archival & Distillation

When ending a conversational session (via `/exit` or `/save`), Sympose distills the entire raw conversation transcript into two distinct, high-value destinations:
1. **Persistent Memory Bullets** (`profiles/{handle}_memory.md`).
2. **Structured Obsidian Session Logs** (`{MASTER_VAULT_PATH}/{vault_folder}/Sessions/YYYY-MM-DD_HHMM_{handle}_session.md`).

---

## 1. The Exit Workflow

When you type `/exit` (or `quit` / `exit`), Sympose presents an interactive choice modal in the terminal:

```
╭────── Save Session Takeaways? ──────╮
│ [1] Persistent Working Memory Only  │
│ [2] Obsidian Vault Session Note     │
│ [3] Both (Memory + Obsidian)        │
│ [4] Discard Session                 │
╰─────────────────────────────────────╯
```

*(Note: You can configure automatic saving on exit by setting `session.exit_behavior.auto_save: true` in `config.yaml` or running `/config set session.exit_behavior.auto_save true`.)*

---

## 2. LLM Transcript Distillation

The [`SessionArchivist`](../../../sympose/memory.py#L117) executes a distillation pass over the conversation transcript, separating signal from conversational noise:

- **Section 1 (Memory Bullets)**: 0–4 permanent facts about the *user* — never the assistant's own actions (tool calls, sub-agents spawned, retrieval steps). The prompt is shown the persona's existing memory file content and told to skip anything already covered, even if it would come out worded differently, and to write `NONE` rather than a bullet list when nothing new qualifies — `'NONE'` naturally produces no bullet lines, so nothing gets appended.
- **Section 2 (Obsidian Session Note)**: A Markdown log formatted with YAML frontmatter, overview, technical decisions, and next steps.

---

## 3. Obsidian Note Template & Frontmatter

Generated Obsidian session notes are written with full YAML metadata:

```markdown
---
type: session-log
persona: samantha
date: 2026-08-24 18:35
model: gemini/gemini-3.6-flash
tags:
  - sympose/session
  - persona/samantha
---

# Session Takeaways: 2026-08-24 18:35

## Overview & Intent
Summary of the discussion and high-level architectural goals.

## Key Decisions & Architecture Highlights
- Summary of technical constraints established during the chat.

## Action Items & Next Steps
- [ ] Immediate follow-up task.
```

---

## 4. Section Bleed Defense & Discrete Memory Standard (ADR-038)

Session distillation prompts are externalized to [`sympose/prompts/session_summary.md`](../../../sympose/prompts/session_summary.md) (shipped inside the package via `package-data`, loaded through `sympose.prompt_assets.load_prompt`).
- **Strict Bullet Filtering**: In `SessionArchivist.summarize_session`, `memory_part` is strictly filtered to bullet points (`- ` / `* `).
- **Zero Pollution**: If section header matching fails or models emit non-bullet prose, raw Markdown notes and headings are never appended into `_memory.md`. The prompt itself is also told never to extract the assistant's own process (tool calls, sub-agent spawns, retrieval/context-configuration steps) as a "fact" — a transcript full of tool narration is not a list of things to remember about the user.
