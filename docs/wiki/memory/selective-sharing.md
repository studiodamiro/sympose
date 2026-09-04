---
title: "Selective Memory Sharing & Privacy Rings"
created: 2026-08-24
type: wiki-memory
parent: memory/index
tags:
  - sympose/memory
  - sympose/privacy
  - adr
---

# 🔒 Selective Memory Sharing & Privacy Rings

In a multi-model personal AI hub, different personas operate under different trust levels:
- **Cloud Models** (Google Gemini, Anthropic Claude) provide massive reasoning bandwidth for engineering and strategy, but send payloads over the network.
- **Local Offline Models** (Ollama / Gemma) run completely air-gapped on your local hardware for private reflections, journaling, and sensitive personal notes.

To prevent private reflections from leaking into cloud prompt payloads while ensuring all agents know who you are, Sympose implements the **Selective Memory Sharing & Privacy Ring Standard (ADR-010)**.

---

## 1. The 3-Tier Memory Topology

```mermaid
graph TD
    subgraph Tier0 [Tier 0: Universal User Card]
        UserCard["profiles/user_profile.md<br/>• Name: damiro<br/>• Environment: macOS Apple Silicon"]
    end

    subgraph Tier1 [Tier 1: Shared Team Memory]
        SharedPool["profiles/_shared_memory.md<br/>• Active Project: Sympose<br/>• Architecture: Modular Python Package"]
    end

    subgraph Tier2 [Tier 2: Private Air-Gapped Stores]
        AuriStore["profiles/aurelius_memory.md<br/>🔒 Personal reflections & Stoic logs"]
        GraceStore["profiles/grace_memory.md<br/>Compiler notes & code reviews"]
        SamStore["profiles/samantha_memory.md<br/>Strategic orchestration"]
    end

    UserCard -->|Read by ALL| Aurelius([@aurelius - Local Ollama])
    UserCard -->|Read by ALL| Grace([@grace - Cloud Gemini/Claude])
    UserCard -->|Read by ALL| Samantha([@samantha - Cloud Gemini])

    SharedPool -->|share_memory: true| Grace
    SharedPool -->|share_memory: true| Samantha
    SharedPool -.->|BLOCKED / share_memory: false| Aurelius

    AuriStore -->|100% Private| Aurelius
    GraceStore --> Grace
    SamStore --> Samantha
```

---

## 2. Configuration & Manifest Controls

Memory sharing is configured per agent via the `share_memory` boolean in [`profiles/*.yaml`](../../../profiles/):

| Agent | Model Backend | `share_memory` | Injected Memories |
| :--- | :--- | :--- | :--- |
| **@samantha** | Cloud (Gemini) | `true` | `user_profile.md` + `_shared_memory.md` + `samantha_memory.md` |
| **@grace** | Cloud (Claude/Gemini) | `true` | `user_profile.md` + `_shared_memory.md` + `grace_memory.md` |
| **@aurelius** | **Local Offline (Ollama)** | `false` | `user_profile.md` + `aurelius_memory.md` *(Air-Gapped)* |

---

## 3. Dynamic Prompt Composition

When [`ProfileManager.build_system_prompt()`](../../../sympose/profiles.py) compiles the prompt for a turn:

1. **Step 1 (Universal Identity)**: Injects [`profiles/user_profile.md`](../../../profiles/user_profile.md).
2. **Step 2 (Shared Team Pool)**: Injects [`profiles/_shared_memory.md`](../../../profiles/_shared_memory.md) **only** if `share_memory: true`.
3. **Step 3 (Persona Memory)**: Injects `profiles/{handle}_memory.md`.
4. **Step 4 (Anti-Hallucination Grounding)**: Enforces strict grounding rules, commanding the agent to admit ignorance if a queried fact is missing from the injected sections.

---

## 4. Memory Persistence & Isolation Guarantees

When new facts are persisted via `[REMEMBER: ...]` tags or shadow extraction:
- If `share_memory: true`, facts are mirrored into both `_shared_memory.md` and the persona's private memory file with line deduplication.
- If `share_memory: false`, facts are written **strictly** to the local persona memory file, guaranteeing **0 data leaks** across cloud boundaries.
