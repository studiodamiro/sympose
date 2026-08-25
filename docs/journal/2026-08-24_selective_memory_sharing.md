---
entry: 2026-08-24
created: 2026-08-24 19:45
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/memory
  - sympose/privacy
  - adr
---

# Sympose Engineering Log: Selective Memory Sharing & Universal User Profile

> **Date:** Monday, August 24, 2026  
> **Topic:** ADR-010 Selective Memory Sharing & Universal User Profile Architecture  
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)  
> **Status:** Implemented, Tested & Verified (All Modules < 200 LOC)  

---

## 1. Executive Summary

During live testing with `@aurelius` (local Ollama), an amnesia issue surfaced: Aurelius did not know the user's name (`damiro`), while cloud personas (`@samantha` and `@grace`) did. Furthermore, user requirements dictated that while `@grace` and `@samantha` should collaborate and share project knowledge, `@aurelius` operates as a private, offline confidant whose personal journaling and sensitive memories must never leak to cloud LLMs.

To solve both challenges without token bloat or privacy compromise, we designed and implemented **ADR-010: Selective Memory Sharing & Universal User Profile Architecture**:
1. **Universal User Card (`profiles/user_profile.md`)**: A lightweight identity profile loaded automatically by **all** agents, guaranteeing universal user awareness (name, OS, core workflow style) from Turn 1.
2. **Configurable Memory Sharing (`share_memory: true | false`)**:
   - `share_memory: true` ([`samantha.yaml`](./profiles/samantha.yaml) & [`grace.yaml`](./profiles/grace.yaml)): Injects and syncs with `profiles/_shared_memory.md` for multi-agent project collaboration.
   - `share_memory: false` ([`aurelius.yaml`](./profiles/aurelius.yaml)): Keeps memory strictly air-gapped within `profiles/aurelius_memory.md`, with zero cross-talk to cloud shared files.

---

## 2. Architectural Decision Record (ADR-010)

### ADR-010: Selective Memory Sharing & Universal User Profile Architecture

#### Context & Problem Statement
* Personal multi-agent hubs host diverse models across distinct trust tiers (e.g. Cloud APIs like Claude 3.5 Sonnet / Gemini vs. Local Air-Gapped Ollama models).
* If memory is 100% isolated per agent, every new agent suffers from amnesia regarding the user's name and core setup.
* If memory is 100% global, local private reflections (e.g. Stoic journaling with Aurelius) are leaked into prompt payloads sent to third-party cloud APIs during engineering sessions.

#### Decision
* **Dual-Tier Memory Composition in `ProfileManager.build_system_prompt()`**:
  1. **Tier 0 (Universal User Profile)**: `profiles/user_profile.md` is injected into every agent prompt. Contains only non-sensitive identity metadata (`Name: damiro`, `Environment: macOS`).
  2. **Tier 1 (Shared Team Memory Pool)**: Injected **only** if the persona manifest declares `share_memory: true`.
  3. **Tier 2 (Persona Private Memory)**: Injected from `profiles/{handle}_memory.md`.
* **Isolated Memory Appends**:
  - `ProfileManager.append_memory(handle, fact)` checks `profile.get("share_memory")`. If `False`, the fact is written exclusively to the local `{handle}_memory.md`. If `True`, it is mirrored to `_shared_memory.md`.
* **ActionProcessor Badge Clarity**:
  - Confirms whether facts were stored to private memory or synced to shared team memory.

#### Consequences
* **Positive**: Aurelius and all future agents instantly know who the user is without manual re-introduction.
* **Positive**: 100% privacy guarantee for local offline agents (`aurelius_memory.md` is strictly air-gapped from cloud prompts).
* **Positive**: Full project synergy between engineering and orchestration agents (Grace and Samantha).

---

## 3. Memory Layout & Sharing Topology

```mermaid
graph TD
    User([damiro]) --> Chat[Sympose CLI / Slack]
    
    subgraph Universal [Tier 0: Universal Identity]
        UserProfile[profiles/user_profile.md<br/>Name: damiro, macOS]
    end

    subgraph SharedTeam [Tier 1: Shared Team Pool]
        SharedMem[profiles/_shared_memory.md<br/>Sympose Architecture, Tech Stack]
    end

    subgraph PrivateStores [Tier 2: Private Isolated Memories]
        AuriMem[profiles/aurelius_memory.md<br/>🔒 Stoic Reflections, Offline Only]
        GraceMem[profiles/grace_memory.md<br/>Engineering Directives]
        SamMem[profiles/samantha_memory.md<br/>Strategy Directives]
    end

    UserProfile -->|Injected to ALL| AuriLLM[Aurelius / Gemma2:9b]
    UserProfile -->|Injected to ALL| GraceLLM[Grace / Gemini/Claude]
    UserProfile -->|Injected to ALL| SamLLM[Samantha / Gemini]

    SharedMem -->|share_memory: true| GraceLLM
    SharedMem -->|share_memory: true| SamLLM
    SharedMem -.->|BLOCKED / share_memory: false| AuriLLM

    AuriMem -->|Air-Gapped| AuriLLM
    GraceMem --> GraceLLM
    SamMem --> SamLLM
```

---

## 4. Verification & Benchmarks

* **Automated Test Suite ([`scratch/test_selective_memory.py`](./scratch/test_selective_memory.py))**:
  * Universal User Profile awareness across all personas: **PASSED**
  * Shared Team Memory injection for Samantha & Grace: **PASSED**
  * Privacy Air-Gap validation for Aurelius (0 leaks to `_shared_memory.md`): **PASSED**
  * Selective memory append routing: **PASSED**
  * ActionProcessor badge formatting: **PASSED**
* **LOC Compliance**:
  * All 10 modules in `sympose/` strictly under 200 lines (1,388 total LOC).
