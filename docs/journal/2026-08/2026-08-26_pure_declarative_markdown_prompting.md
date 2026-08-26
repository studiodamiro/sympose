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

## 2. Architectural Decisions (ADR-037)

### ADR-037.1: 100% Hands-Off Python Principle
* Python files are strictly **transport runners, file assemblers, and LiteLLM/Slack conduits**.
* **Zero hardcoded prompt text in Python**: All instructions, spatial coordinates, rules, and system prompts live purely in editable Markdown documents.

### ADR-037.2: Universal Workspace Rules (`workspace_rules.md`)
* All global spatial rules, strict anti-hallucination protocols, and autonomic action execution tags (`[REMEMBER]`, `[WRITE_NOTE]`, `[DAILY_NOTE]`, `[SPAWN_WORKER]`, `[CONFIG_SET]`, `[CREATE_PERSONA]`, `[DELETE_PERSONA]`) live in the root [`workspace_rules.md`](../../workspace_rules.md).
* `ProfileManager` dynamically substitutes runtime variables (`{{workspace_root}}`, `{{master_vault_path}}`, `{{sandboxed_vault}}`, `{{user}}`, `{{handle}}`, `{{name}}`).

### ADR-037.3: Modular Template Directory (`prompts/`)
* Standardized prompt templates are organized into `prompts/`:
  - [`prompts/memory_extraction.md`](../../prompts/memory_extraction.md): Background shadow fact extractor.
  - [`prompts/session_summary.md`](../../prompts/session_summary.md): Two-section session summarization format.
  - [`prompts/worker_system.md`](../../prompts/worker_system.md): Ephemeral sub-agent worker directives.

---

## 3. Verification & Results

* All prompt assembling and template loading passed automated verification (`test_prompt_assembly.py`).
* Codebase line counts were dramatically reduced across `sympose/profiles.py` (170 LOC) and `sympose/memory.py` (145 LOC).
