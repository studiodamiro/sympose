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
1. [`ProfileManager`](file:///Users/damiro/Development/sympose/sympose/profiles.py#L20) detects that `profiles/feynman_soul.md` and `feynman_memory.md` do not exist.
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
  - "Hunting for zero-bloat solutions..."
```
