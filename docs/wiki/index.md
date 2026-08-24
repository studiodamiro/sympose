---
title: "Sympose Wiki: Zero-Bloat Multi-Model AI Agent Hub"
created: 2026-08-24
type: wiki-index
status: published
tags:
  - sympose/wiki
  - portfolio
  - architecture
  - multi-agent
---

# 🏛️ Sympose Wiki
> **A zero-bloat, sub-second personal AI orchestration hub and dynamic memory system.**

Welcome to the technical documentation and engineering specifications for **Sympose**. Sympose is designed as an unbloated, developer-first alternative to heavyweight multi-agent frameworks, pairing ultra-fast cloud models (Google Gemini, Anthropic Claude) with local, private LLMs (Ollama) under a unified CLI, sandboxed Obsidian vault, and autonomous memory layer.

---

## 🗺️ System Architecture Overview

```mermaid
graph TD
    User([User Interactive REPL / Slack]) --> Engine[PersonaEngine]
    
    subgraph Core Execution Loop
        Engine --> PM[ProfileManager]
        Engine --> Archivist[SessionArchivist]
        Engine --> Cmds[CommandInterceptor]
        Engine --> VM[VaultManager]
    end
    
    subgraph Multi-Model Layer [<0.8s SLA]
        Engine --> Gemini[Google Gemini 3.5 Flash-Lite]
        Engine --> Claude[Anthropic Claude 3.5 Sonnet]
        Engine --> Ollama[Local Marcus Aurelius / Ollama]
    end
    
    subgraph Autonomous Memory Triad
        PM --> Manifests[profiles/*.yaml Manifests]
        PM --> Souls[profiles/*_soul.md Directives]
        Archivist --> Shadow[Async Shadow Extractor]
        Shadow --> Memory[profiles/*_memory.md]
    end
    
    subgraph Sandboxed Vault Storage
        VM --> Notes[Obsidian Vault Domain Folders]
        Archivist --> Sessions[Sessions/YYYY-MM-DD_session.md]
    end
```

---

## 📚 Wiki Sections & Deep Dives

### 📐 [Architecture](file:///Users/damiro/Development/sympose/docs/wiki/architecture/overview.md)
* **[System Overview](file:///Users/damiro/Development/sympose/docs/wiki/architecture/overview.md):** The Triad pattern separating UI manifest, cognitive directives, and persistent memory.
* **[Sub-Second Latency Engine](file:///Users/damiro/Development/sympose/docs/wiki/architecture/sub-second-engine.md):** How Sympose achieves 0.75s TTFT on macOS by eliminating GCE metadata server hangs and managing warm connection pools.
* **[MCP & Sub-Agent Workers](file:///Users/damiro/Development/sympose/docs/wiki/architecture/mcp-and-workers.md):** Isolated, ephemeral worker sandboxes connecting to Model Context Protocol tool servers.
* **[Sandboxed Obsidian Vault](file:///Users/damiro/Development/sympose/docs/wiki/architecture/sandboxed-vault.md):** Defensive path validation, isolated domain folders, and note search tiers.

### 🧠 [Autonomous Memory System](file:///Users/damiro/Development/sympose/docs/wiki/memory/shadow-extractor.md)
* **[Selective Memory Sharing & Privacy Rings](file:///Users/damiro/Development/sympose/docs/wiki/memory/selective-sharing.md):** Air-gapping private offline agents (Aurelius) while allowing cloud agents (Samantha & Grace) to share team project memory.
* **[Heuristic Gated Shadow Extractor](file:///Users/damiro/Development/sympose/docs/wiki/memory/shadow-extractor.md):** Frictionless, zero-keyword memory capture running in detached background daemon threads.
* **[Anti-Hallucination & Grounding](file:///Users/damiro/Development/sympose/docs/wiki/memory/anti-hallucination.md):** Eliminating sycophancy with the 4 grounding pillars and honest ignorance protocols.
* **[Session Archival & Distillation](file:///Users/damiro/Development/sympose/docs/wiki/memory/session-archival.md):** Automated session logs and working memory consolidation on exit.

### 🎭 [Persona & Skills Ecosystem](file:///Users/damiro/Development/sympose/docs/wiki/agents/profile-system.md)
* **[Profile System & Auto-Bootstrapping](file:///Users/damiro/Development/sympose/docs/wiki/agents/profile-system.md):** Spinning up new domain specialists with a minimal 4-line YAML manifest.
* **[Modular Skills System (`SKILL.md`)](file:///Users/damiro/Development/sympose/docs/wiki/agents/skills-system.md):** Reusable procedural heuristics, domain playbooks, and tool bindings.
* **[@samantha](file:///Users/damiro/Development/sympose/docs/wiki/agents/samantha.md):** Strategic Master Orchestrator.
* **[@grace](file:///Users/damiro/Development/sympose/docs/wiki/agents/grace.md):** Surgical Software Engineer.
* **[@aurelius](file:///Users/damiro/Development/sympose/docs/wiki/agents/aurelius.md):** 100% Offline Local Sounding Board.

### 🚀 [Guides & Getting Started](file:///Users/damiro/Development/sympose/docs/wiki/guides/quickstart.md)
* **[Quickstart Guide](file:///Users/damiro/Development/sympose/docs/wiki/guides/quickstart.md):** Installation, API keys, and starting the interactive CLI.
* **[Configuration](file:///Users/damiro/Development/sympose/docs/wiki/guides/configuration.md):** Centralized `config.yaml` and dynamic in-session tuning.
* **[Creating Custom Agents](file:///Users/damiro/Development/sympose/docs/wiki/guides/creating-agents.md):** Defining new persona models, prompts, and vault permissions.

### 📖 [Reference](file:///Users/damiro/Development/sympose/docs/wiki/reference/cli-commands.md)
* **[CLI Commands & Shortcuts](file:///Users/damiro/Development/sympose/docs/wiki/reference/cli-commands.md):** Complete guide to `/save`, `/config`, `/switch`, `/note`, `/daily`, and `/ask`.
* **[Python API Reference](file:///Users/damiro/Development/sympose/docs/wiki/reference/python-api.md):** Package internals, class hierarchies, and integration hooks.
