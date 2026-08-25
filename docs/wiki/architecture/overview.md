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

## 2. The Zero-Maintenance Mandate (The Assistant Paradox)

> **"If the user has to become the sysadmin, curator, or custodian of their AI assistant, the system is actively working against its primary reason for existing."**

Sympose enforces the **Zero-Maintenance Mandate** across every subsystem:
1. **Self-Healing & Auto-Bootstrapping**: If a new specialist profile is created with a minimal YAML manifest, missing soul and memory files are automatically generated on boot.
2. **Autonomous Memory Hygiene**: Memory files are compacted, deduplicated, and pruned in non-blocking background daemon threads by the `MemoryCompactor` without requiring user curation.
3. **Dynamic Model Discovery**: `ModelCatalog` queries and caches OpenRouter's live catalog on-demand. There are zero hardcoded model dictionaries to manually update.
4. **Zero Infrastructure Daemons**: Sympose runs directly on Python standard library primitives over local Markdown files. There are zero background Postgres, Redis, Docker, or vector database servers to maintain, crash, or migrate.
5. **Self-Regulating Context**: Sliding context window governors automatically prevent token bloat without requiring manual `/clear` micromanagement.

---

## 3. Package Layering & Modular Design

The Sympose codebase enforces a strict **Single Responsibility Principle (SRP)** with a hard architectural constraint: **no source file exceeds 200 lines of code**.

| Module | LOC | Responsibility |
| :--- | :---: | :--- |
| [`app.py`](./app.py) | 40 | CLI argument parsing and entrypoint launcher. |
| [`sympose/config.py`](./sympose/config.py) | 148 | Master configuration loading, LiteLLM sync, and OS environment optimization. |
| [`sympose/profiles.py`](./sympose/profiles.py) | 197 | YAML profile discovery, auto-bootstrapping, and prompt compilation. |
| [`sympose/engine.py`](./sympose/engine.py) | 195 | Multi-model streaming, sliding context windows, and sub-agent delegation. |
| [`sympose/compactor.py`](./sympose/compactor.py) | 108 | Autonomous background working memory compaction and conflict resolution. |
| [`sympose/models.py`](./sympose/models.py) | 102 | OpenRouter catalog discovery, disk caching, and live keyword search. |
| [`sympose/memory.py`](./sympose/memory.py) | 192 | Heuristic gated shadow extraction and session archival. |
| [`sympose/skills.py`](./sympose/skills.py) | 145 | Modular procedural playbooks (`skills/`) and dynamic prompt injection. |
| [`sympose/mcp.py`](./sympose/mcp.py) | 188 | Model Context Protocol JSON-RPC 2.0 stdio client and tool bridge. |
| [`sympose/workers.py`](./sympose/workers.py) | 188 | Ephemeral sub-agent worker execution sandbox with skill model auto-resolution. |
| [`sympose/native_tools.py`](./sympose/native_tools.py) | 85 | Deterministic native execution tools (`run_command`, `read_file`). |
| [`sympose/vault.py`](./sympose/vault.py) | 176 | Sandboxed file I/O, path traversal defenses, and multi-tier vault search. |
| [`sympose/commands.py`](./sympose/commands.py) | 372 | Slash command interceptors (`/model`, `/compact`, `/worker`, `/save`, `/config`). |
| [`sympose/completer.py`](./sympose/completer.py) | 195 | Interactive Readline Tab completion for commands, personas, models, and skills. |
| [`sympose/cli.py`](./sympose/cli.py) | 168 | Interactive Rich streaming terminal REPL and exit workflows. |
| [`sympose/ui.py`](./sympose/ui.py) | 77 | Rich visual components, persona selection table, and banners. |
