---
title: "Agent Profile System & Autonomous Genesis"
created: 2026-08-24
type: wiki-agents
parent: index
tags:
  - sympose/agents
  - profiles
  - auto-bootstrapping
---

# 🎭 Agent Profile System & Autonomous Genesis

Creating new specialist agents in Sympose requires zero boilerplate. You do not need to manually craft three synchronized files (`.yaml`, `_soul.md`, `_memory.md`). Sympose supports **Autonomous Genesis (Method A)**.

---

## 1. Minimal 4-Line Agent Manifest

To add a new agent, simply drop a minimal YAML file into `profiles/`:

```yaml
# profiles/feynman.yaml
name: "Richard Feynman"
handle: "feynman"
title: "First-Principles Physics & Intuition Master"
model: "gemini/gemini-3.5-flash-lite"
```

---

## 2. Autonomous Bootstrapping on First Boot

When Sympose launches or reloads:
1. [`ProfileManager`](./sympose/profiles.py#L20) detects that `profiles/feynman_soul.md` and `feynman_memory.md` do not exist.
2. **Auto-Soul Genesis**: Synthesizes a structured `profiles/feynman_soul.md` file defining domain authority, tone, and heuristics.
3. **Auto-Memory Genesis**: Seeds `profiles/feynman_memory.md` with role context.
4. **Thinking Phrases**: Injects themed status spinner phrases into the runtime profile.

---

## 3. Full Manifest Specification

For advanced customization, a full YAML manifest supports:

```yaml
name: "Grace Hopper"
handle: "grace"
title: "Surgical Software Engineer"
model: "gemini/gemini-3.5-flash-lite"
icon_emoji: "🛠️"
vault_folder: "Engineering"
temperature: 0.1
soul_file: "profiles/grace_soul.md"
memory_file: "profiles/grace_memory.md"

thinking_phrases:
  - "Decompiling assumptions..."
  - "Eliminating unnecessary abstractions..."
  - "Refactoring logic paths..."

skills:
  - "git_workflow"
  - "code_review"

vault_folders:
  - "General"
  - "Engineering"

share_memory: true
```

---

## 4. The 7-Point Master Agent Prerequisite Standard

Every complete, production-grade agent in Sympose satisfies seven foundational architectural pillars:

| # | Prerequisite | Responsibility & Standard |
| :--- | :--- | :--- |
| **1** | **Identity & Manifest** | Unique handle (`@handle`), display name, role title, and fast LLM model (`gemini-3.5-flash-lite`, `claude-3-5-sonnet`, `ollama/gemma2`). |
| **2** | **Soul Directives (`_soul.md`)** | Distinct tone, role authority, domain heuristics, worker delegation directives, and strict anti-hallucination boundaries. |
| **3** | **Working Memory (`_memory.md`)** | Mode selection (`share_memory: true` for team collaboration; `false` for air-gapped private reflection), linked to universal user card. |
| **4** | **Obsidian Vault Sandbox** | Explicit domain folder whitelist (`vault_folders: [...]`) or root access (`["*"]`), verified on disk. |
| **5** | **Procedural Skills** | Reusable domain playbooks mounted from `skills/` (e.g. `strategic_analysis`, `git_workflow`). |
| **6** | **Tool & MCP Dependencies** | Corresponding MCP servers declared in `config.yaml` and required API keys present in `.env`. |
| **7** | **Interactive Spinners** | 3–5 domain-flavored status phrases for responsive CLI feedback. |

---

## 5. Conversational Agent Creation (Samantha Concierge)

Non-technical users do not need to create YAML files manually. They can ask Samantha in natural language:

```text
You (to @samantha): Sam, please create a new research agent named "Curie" with access to the Research folder.
```

Samantha verifies whether the `Research/` folder exists in your Obsidian vault, emits `[CREATE_PERSONA: curie | ...]`, and you can immediately switch to the new agent using `/switch @curie`!

---

## 6. Safe Agent Deletion & Retirement

To keep the active agent roster clean without risking data loss, Sympose implements a **Defensive Soft-Delete Standard**:

* **Archival Sandbox (`profiles/_archived/<handle>/`)**: When an agent is retired, their files (`.yaml`, `_soul.md`, `_memory.md`) are moved into `profiles/_archived/<handle>/`.
* **Vault Preservation**: Notes previously written into your Obsidian vault are never deleted.
* **Protected Personas**: `@samantha` is the permanent master orchestrator and cannot be deleted.

### Triggering Deletion:
1. **Via Slash Command**:
   ```bash
   /delete @curie
   # or
   /retire @curie
   ```
2. **Via Natural Language with Samantha**:
   ```text
   You (to @samantha): Sam, I no longer need Curie. Please retire her.
   # Samantha emits [DELETE_PERSONA: curie]
   ```
