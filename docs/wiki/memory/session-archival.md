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

The [`SessionArchivist`](./sympose/memory.py#L90) executes a distillation pass over the conversation transcript, separating signal from conversational noise:

- **Section 1 (Memory Bullets)**: 2–4 permanent facts or decisions appended to working memory.
- **Section 2 (Obsidian Session Note)**: A Markdown log formatted with YAML frontmatter, overview, technical decisions, and next steps.

---

## 3. Obsidian Note Template & Frontmatter

Generated Obsidian session notes are written with full YAML metadata:

```markdown
---
type: session-log
agent: samantha
date: 2026-08-24 18:35
model: gemini/gemini-3.5-flash-lite
tags:
  - sympose/session
  - agent/samantha
---

# Session Takeaways: 2026-08-24 18:35

## Overview & Intent
Summary of the discussion and high-level architectural goals.

## Key Decisions & Architecture Highlights
- Summary of technical constraints established during the chat.

## Action Items & Next Steps
- [ ] Immediate follow-up task.
```
