---
title: "ADR-010 — Selective Memory Sharing & Universal User Profile Architecture"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-010 — Selective Memory Sharing & Universal User Profile Architecture

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

A personal multi-agent hub mixes trust tiers: cloud APIs (Claude, Gemini) and
local air-gapped Ollama models. Fully isolated memory gives every new agent
amnesia about the user's name and setup. Fully global memory leaks private
offline reflections (e.g. Stoic journaling with `@aurelius`) into third-party
cloud prompts.

## Decision

Dual-tier memory composition in `ProfileManager.build_system_prompt()`:

- **Tier 0 — Universal user profile.** `profiles/user_profile.md` (non-sensitive
  identity only: name, OS, workflow style) is injected into every agent.
- **Tier 1 — Shared team memory.** `profiles/_shared_memory.md` is injected
  **only** when the manifest declares `share_memory: true`.
- **Tier 2 — Persona private memory.** `profiles/{handle}_memory.md`, always.

`append_memory(handle, fact)` routes by `share_memory`: `false` writes only to
the local file; `true` mirrors to `_shared_memory.md`. Badges state which store
was written.

## Consequences

**Positive**

- Every agent knows the user from turn 1 with no re-introduction.
- Offline agents are 100% air-gapped from cloud prompt payloads.
- Cloud collaborators (Samantha, Grace) share project context freely.

**Negative / costs**

- Three composition tiers to assemble per prompt; `share_memory` must be set
  correctly per manifest or privacy/utility silently degrades.

## Alternatives rejected

- **100% per-agent isolated memory.** Rejected: every new agent has amnesia
  about basic user identity.
- **100% global shared memory.** Rejected: leaks private offline reflections
  into cloud API payloads.
