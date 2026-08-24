---
title: "Architecture Overview & The Triad Pattern"
created: 2026-08-24
type: wiki-architecture
parent: index
tags:
  - sympose/architecture
  - system-design
  - triad-pattern
---

# 📐 Architecture Overview & The Triad Pattern

Sympose is designed around strict separation of concerns. Instead of stuffing prompt instructions, API configurations, personality, and memory into a single monolithic file or database row, Sympose separates agent intelligence into three distinct, specialized file formats: the **Triad Pattern**.

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Profile Manifest (yaml)  ──>  RUNTIME / UI METADATA      │
│    • Name, Handle, Title, Icon, Model, Vault Folder         │
│    • thinking_phrases: UI spinner strings (0 token cost)    │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent Soul (_soul.md)   ──>  COGNITIVE DIRECTIVES        │
│    • Injected into LLM System Prompt                        │
│    • Inflexible tone, reasoning heuristics, boundaries      │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│ 3. Working Memory (_memory)──>  DYNAMIC EVOLVING FACTS      │
│    • Updated live by Shadow Extractor & /exit Archival      │
│    • Decayed and consolidated over time                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Why The Triad Pattern Matters

### 1. Zero-Cost Presentation Metadata
UI presentation strings (like terminal status spinners, Slack avatar URLs, and domain vault folders) live exclusively in the `profiles/{handle}.yaml` manifest. The LLM never reads these strings in its system prompt, saving valuable context tokens and eliminating pre-fill latency.

### 2. Immutable Soul vs. Mutable Memory
- **The Soul (`_soul.md`)** is static and deliberate. It defines who the agent is, how it reasons, and its communication philosophy.
- **The Memory (`_memory.md`)** is dynamic. It mutates silently as you work, capturing user plans, technical decisions, and preferences.

### 3. File-Based & Obsidian-Native
Everything in Sympose is a standard Markdown or YAML file stored locally on disk. You can open `profiles/` or your vault in Obsidian, VS Code, or Git. There is zero proprietary database lock-in.

---

## 2. Package Layering & Modular Design

The Sympose codebase enforces a strict **Single Responsibility Principle (SRP)** with a hard architectural constraint: **no source file exceeds 200 lines of code**.

| Module | LOC | Responsibility |
| :--- | :---: | :--- |
| [`app.py`](file:///Users/damiro/Development/sympose/app.py) | 40 | CLI argument parsing and entrypoint launcher. |
| [`sympose/config.py`](file:///Users/damiro/Development/sympose/sympose/config.py) | 148 | Master configuration loading, LiteLLM sync, and OS environment optimization. |
| [`sympose/profiles.py`](file:///Users/damiro/Development/sympose/sympose/profiles.py) | 197 | YAML profile discovery, autonomous genesis, memory deduplication, and prompt compilation. |
| [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py) | 186 | Multi-model execution engine, sliding context windows, and sub-agent delegation. |
| [`sympose/memory.py`](file:///Users/damiro/Development/sympose/sympose/memory.py) | 185 | Heuristic gated shadow extraction and full-transcript session archival. |
| [`sympose/vault.py`](file:///Users/damiro/Development/sympose/sympose/vault.py) | 176 | Sandboxed file I/O, path traversal defenses, and multi-tier vault search. |
| [`sympose/commands.py`](file:///Users/damiro/Development/sympose/sympose/commands.py) | 173 | Command interception (`/save`, `/config`, `/vault`, `/switch`). |
| [`sympose/cli.py`](file:///Users/damiro/Development/sympose/sympose/cli.py) | 168 | Interactive Rich streaming terminal REPL and exit workflows. |
| [`sympose/ui.py`](file:///Users/damiro/Development/sympose/sympose/ui.py) | 77 | Rich visual components, persona selection table, and banners. |
