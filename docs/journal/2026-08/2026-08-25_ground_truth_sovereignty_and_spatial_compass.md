---
entry: 2026-08-25
created: 2026-08-25 17:05
type: adr-log
project: sympose
tags:
  - adr
  - architecture
  - grounding
  - vault-recall
  - spatial-compass
  - anti-hallucination
---

# Architecture Decision Records: Ground-Truth Sovereignty & Config-Driven Spatial Compass

> **Date:** 2026-08-25  
> **Author:** damiro & Grace Hopper  
> **Status:** Ratified & Implemented  
> **Affected Modules:** `sympose/engine.py`, `sympose/vault.py`, `sympose/workers.py`, `sympose/native_tools.py`, `sympose/skills.py`, `skills/vault_recall/SKILL.md`, `profiles/*.yaml`, `profiles/aurelius_soul.md`

---

## Executive Summary

During live testing of historical note retrieval with `@aurelius` (`ollama/gemma2:9b`) and movie review retrieval with `@samantha` (`gemini/gemini-3.5-flash-lite`), two critical systemic failure modes were identified:
1. **The Follow-Up Context Wipe & 9B Roleplay Fallback**: When conversational follow-ups (*"just pick one"*, *"show me the text"*) were issued, pre-turn search results were cleared from the prompt, causing local 9B models to hallucinate fake notes (`2017-10-26`) or simulate action progress (`*[Begins retrieval]*`, `*Outputs full text...*`).
2. **The Worker Workspace Trap & Query Preamble Swallowing**: Sub-agent workers ran in `os.getcwd()` (`sympose`) instead of the vault (`garden`), while natural conversational preambles (*"i heard you can retrieve a note from our obsidian vault..."*) polluted the search query.

This journal establishes four Architectural Decision Records (**ADR-024** through **ADR-027**) that resolve these failures, enshrine the **Ground-Truth Sovereignty Axiom**, and implement the **Config-Driven Spatial Compass**.

---

## Architectural Decision Records

- **[ADR-024 — The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives](./2026-08-25_adr-024-ground-truth-sovereignty-axiom.md):**
  Markdown on disk is the sovereign source of truth; verbatim blockquote
  quotation; zero fabrication or simulated actions when a note is absent.
- **[ADR-025 — Persistent Multi-Turn Vault Context & Conversational Intent Stripping](./2026-08-25_adr-025-persistent-multi-turn-vault-context.md):**
  `PersonaEngine.active_vault_ctx` keeps turn-1 notes across follow-ups; a
  greeting/preamble normalizer isolates the real topic keyword.
- **[ADR-026 — Sub-Agent Worker Spatial Environment & Inherited Sandbox Security](./2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md):**
  workers inherit the parent's `allowed_dirs` (zero-escalation), get the vault
  path injected, and use a vault-aware file reader; fuzzy skill-name resolution
  and installed-weight model alignment. Rejects unrestricted workers.
- **[ADR-027 — Config-Driven Spatial Compass & Complete Vault Agnosticism](./2026-08-25_adr-027-config-driven-spatial-compass.md):**
  zero hardcoded paths in `sympose/`; all spatial config in `.env` /
  `config.yaml`; dynamic discovery for Flat / PARA / Johnny Decimal /
  Zettelkasten; portability via one `MASTER_VAULT_PATH`.

---

## System Metrics & Compliance
* All modified Python files remain strictly within the `<200 LOC` architectural mandate (`engine.py`: 193 LOC, `vault.py`: 199 LOC, `workers.py`: 194 LOC, `skills.py`: 168 LOC, `native_tools.py`: 127 LOC).
* Live end-to-end verified across both local Ollama models (`gemma2:9b`, `qwen2.5:14b`) and cloud models (`gemini-3.5-flash-lite`).
