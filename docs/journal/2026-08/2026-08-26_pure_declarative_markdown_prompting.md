---
entry: 2026-08-26
created: 2026-08-26 19:15
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - prompts
  - markdown-driven
  - clean-architecture
  - adr-037
---

# Engineering Journal: Pure Declarative Markdown-Driven Prompting & Zero-Code Injections (ADR-037)

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace Hopper / Samantha  
> **Status:** APPROVED & IMPLEMENTED (ADR-037)  

---

## 1. Context & Problem Statement

Prior to ADR-037, `sympose/*.py` files contained over 120 lines of hardcoded English prompt strings and runtime instructions embedded directly in Python code:
1. `sympose/profiles.py` hardcoded 35+ lines of spatial coordinates, grounding rules, and autonomic action tag instructions.
2. `sympose/memory.py` hardcoded prompt strings for background fact extraction and session summarization.
3. `sympose/workers.py` hardcoded system directives for ephemeral sub-agent workers.

This created **prompt clutter, code coupling, and poor transparency**: modifying agent instructions or tuning summarization required editing Python source files.

---

## 2. Architectural Decisions

- **[ADR-037 — Pure Declarative Markdown-Driven Prompting & Zero-Code Injections](./2026-08-26_adr-037-pure-declarative-markdown-prompting.md):**
  100% hands-off Python — zero hardcoded prompt text (037.1); universal
  `workspace_rules.md` with `{{variable}}` substitution (037.2); a modular
  `prompts/` template directory (037.3).

---

## 3. Verification & Results

* All prompt assembling and template loading passed automated verification (`test_prompt_assembly.py`).
* Codebase line counts were dramatically reduced across `sympose/profiles.py` (170 LOC) and `sympose/memory.py` (145 LOC).
