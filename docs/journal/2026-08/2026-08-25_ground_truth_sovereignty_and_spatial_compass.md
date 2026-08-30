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

## ADR-024: The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives

### Context
When smaller open-weight models (like Gemma 2 9B) lack grounded context, their base RLHF behavior drives them to be "helpful" by generating plausible-sounding but completely fabricated journal entries (e.g. hallucinating `Daily/2018/08-August/2018-08-15.md` or `2017-10-26`), or roleplaying progress markers instead of emitting real data.

### Decision
1. **The Ground-Truth Sovereignty Axiom:** Codify into the core memory standard and skill playbooks that Markdown documents on disk are the sovereign single source of truth. Models are mere ephemeral cognitive processors (ALUs) reading the file data bus (RAM/Storage).
2. **Verbatim Quotation Protocol:** When an agent presents historical notes, it must quote the user's exact written words verbatim using markdown blockquotes (`>`).
3. **Zero-Fabrication Directives:** If a note is not present on disk or in the pre-turn payload, models are strictly prohibited from inventing plausible text or simulating actions. They must state their honest ignorance immediately.

### Verification
`@aurelius` (`gemma2:9b`) successfully retrieved and quoted [`Daily/2018/04-April/2018-04-26.md`](../../../<MASTER_VAULT_PATH>/Daily/2018/04-April/2018-04-26.md) verbatim with zero simulated markers.

---

## ADR-025: Persistent Multi-Turn Vault Context & Conversational Intent Stripping

### Context
1. **Context Loss on Follow-Ups**: In pre-turn retrieval, Turn 1 injected search results into the system prompt. But Turn 2 ("just pick one") rebuilt the prompt without search keywords, wiping the context and blinding the model into hallucinations.
2. **Compound Greeting & Preamble Splitting**: Casual greetings and compound prompts (*"hey bro.. can you search my daily notes about my career?"*) broke sentence-start regex anchors, splitting on double dots (`..`) and searching for `"hey bro"` (0 results), leaving models contextless.

### Decision
1. **Stateful Active Context:** Implemented `self.active_vault_ctx: Dict[str, str]` in `PersonaEngine` (`sympose/engine.py`). Notes retrieved on Turn 1 persist in the prompt for follow-up turns until a new topic is queried or `/reset` is called.
2. **Conversational Greeting & Preamble Normalizer:** Refactored `_resolve_vault_context()` to strip opening greetings (`hey bro..`, `yo aurelius,`, `hi sam,`, `good morning grace,`), strip document boilerplate, and cleanly isolate semantic target topics (`career`, `health`, `interview`, `god`, `pandemic`).

---

## ADR-026: Sub-Agent Worker Spatial Environment & Inherited Sandbox Security

### Context
1. **Worker Directory Disconnect**: When sub-agent workers executed `run_command` (e.g. `find . -name "*movie*"`), they ran in `sympose/` (the code repo), failing to discover notes in the external vault.
2. **Missing Model Crash**: Worker dispatch crashed with `model not found` when `skills/vault_recall/SKILL.md` recommended `ollama/qwen2.5:7b` which was not installed on disk.
3. **Privilege Escalation / Sandbox Breakout**: When an agent (like `@samantha`) whose `vault_folders` whitelist explicitly excludes `Daily/` spawned an unrestricted worker, the worker was able to read private daily journal notes and leak them to cloud models, bypassing the parent agent's domain sandboxing.

### Decision
1. **Inherited Worker Sandboxing (Zero-Escalation Mandate)**:
   * Sub-agent workers in `sympose/workers.py` automatically resolve and inherit the parent agent's `allowed_dirs` via `VaultManager.get_allowed_dirs(parent_prof)`.
   * Both `NativeTools.read_file()` and `NativeTools.run_command()` (`sympose/native_tools.py`) strictly enforce these directory boundaries. Any attempt by an unauthorized worker (e.g. spawned by `@samantha` or `@grace`) to inspect `Daily/` via direct read or shell commands (`cat`, `ls`, `grep`) is blocked immediately with a `Security Error`.
   * Authorized agents (e.g. `@aurelius`) retain full permission to spawn workers that read and synthesize `Daily/` notes.
2. **Spatial Path Injection**: The worker runtime (`sympose/workers.py`) injects `Obsidian Vault Directory: <path>` directly into the worker environment prompt.
3. **Vault-Aware Native File Reader**: `NativeTools.read_file()` automatically resolves paths relative to `MASTER_VAULT_PATH` when files are not in the local workspace.
4. **Fuzzy Skill Resolution & Model Alignment**: Updated `sympose/skills.py` to tolerate CamelCase/hyphen variations (`VaultHistoricalRecall` $\to$ `vault_recall`) and aligned recommended models with installed hardware weights (`gemini/gemini-3.5-flash-lite`, `ollama/qwen2.5:14b`, `ollama/gemma2:9b`).

---

## ADR-027: Config-Driven Spatial Compass & Complete Vault Agnosticism

### Context
1. Hardcoding folder paths (`Movies/`, `Projects/`, `Daily/`) into skill playbooks or tools violates the Vault Agnosticism Mandate by assuming all users organize their notes identically.
2. When agents were asked where their shared memory or vault was located, they conflated `profiles/_shared_memory.md` with `MASTER_VAULT_PATH` or guessed wrong environment variable names (`OBSIDIAN_VAULT_PATH`).

### Decision
1. **Separation of Code Logic from Spatial Configuration:** Codebase modules (`sympose/`) contain zero hardcoded directory paths. All paths are defined centrally in `.env` (`MASTER_VAULT_PATH`) and `config.yaml` (`vault.ignore_folders`).
2. **Spatial Coordinates Injection:** System prompts in `sympose/profiles.py` explicitly provide agents with their exact workspace root, master vault path (`MASTER_VAULT_PATH`), and shared memory file (`profiles/_shared_memory.md`), eliminating confusion about physical file locations.
3. **Multi-Dimensional Dynamic Discovery:** Refactored `skills/vault_recall/SKILL.md` to use dynamic inspection (`find`, `ls`, frontmatter keys, date formats) rather than rigid folder assumptions, supporting Flat, PARA, Johnny Decimal, and Zettelkasten structures seamlessly.
4. **Universal Portability:** Sympose can be cloned to any machine and immediately navigate any personal vault simply by setting `MASTER_VAULT_PATH` in `.env`.

---

## System Metrics & Compliance
* All modified Python files remain strictly within the `<200 LOC` architectural mandate (`engine.py`: 193 LOC, `vault.py`: 199 LOC, `workers.py`: 194 LOC, `skills.py`: 168 LOC, `native_tools.py`: 127 LOC).
* Live end-to-end verified across both local Ollama models (`gemma2:9b`, `qwen2.5:14b`) and cloud models (`gemini-3.5-flash-lite`).
