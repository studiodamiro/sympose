---
title: "Anti-Hallucination & Honest Ignorance Protocol"
created: 2026-08-24
type: wiki-memory
parent: index
tags:
  - sympose/grounding
  - anti-hallucination
  - prompt-engineering
---

# 🛡️ Anti-Hallucination & Honest Ignorance Protocol

Base LLMs are trained to be "helpful and agreeable" (sycophancy). When asked *"Do you remember X?"*, a base LLM defaults to guessing or fabricating details (e.g. inventing a study plan) rather than admitting it has no record.

In Sympose, guessing is treated as a **critical system failure**.

---

## 1. The 5 Grounding & Persistence Pillars

```
┌─────────────────────────────────────────────────────────────┐
│ 1. THE AMNESIA BOUNDARY                                     │
│    The agent is instructed that it has zero organic memory  │
│    outside of `### Persistent Working Memory:` and turns.   │
├─────────────────────────────────────────────────────────────┤
│ 2. ZERO TOLERANCE FOR GUESSING                              │
│    Guessing or fabricating unrecorded user plans is fatal.  │
├─────────────────────────────────────────────────────────────┤
│ 3. CANDID IGNORANCE PROTOCOL                                │
│    If missing, output: "I have no record of that.           │
│    Tell me what it is and I'll log it."                     │
├─────────────────────────────────────────────────────────────┤
│ 4. TEMPERATURE DISCIPLINE                                   │
│    Set `temperature: 0.1` for factual & engineering agents. │
├─────────────────────────────────────────────────────────────┤
│ 5. ASSUME INTERRUPTION (Write-Through State Persistence)    │
│    Context windows are bounded & volatile. Proactively     │
│    checkpoint architectural decisions & facts to disk.      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. The Universal System Prompt Grounding Directive

Every agent system prompt compiled by [`ProfileManager.build_system_prompt`](../../../sympose/profiles.py) carries the **Grounding & Anti-Hallucination** block from [`sympose/prompts/workspace_rules.md`](../../../sympose/prompts/workspace_rules.md) (packaged; the user-editable copy at `~/.sympose/prompts/workspace_rules.md` wins when present). It is non-negotiable:

```markdown
### Grounding & Anti-Hallucination
The vault and the user's history are a document you read, never one you remember.
Every claim about them is a verbatim quote or it is nothing.

1. Your knowledge of the user is exactly {{sources}} plus the active turns — nothing else.
2. State a fact about a note only from a payload given this turn — a
   `### Ground-Truth Sandboxed Vault Note`, `### Ground-Truth Vault Search Results`,
   or a Sub-Agent Worker Report. Quote paths, dates, names, and wording exactly.
   Never reconstruct a note from the topic, the conversation, or what sounds plausible.
3. No payload → don't guess. Not shown the note: say so and emit
   `[SPAWN_WORKER: vault_recall | <subject>]`. Retrieval empty: "I have no record
   of that in your vault." Never use `[SEARCH]` (web) for the user's own notes.
4. Emit `[SEARCH]` / `[SPAWN_WORKER]`, then stop — you have not seen the result yet.
```

Two layers back the prompt up so it holds on a weak/abliterated local model, not
only a strong cloud one:

- **Retrieval** (`VaultManager.resolve_turn_context` / `_recall_hit`) prefers to
  inject the **full verbatim note body** as the pre-turn `### Ground-Truth
  Sandboxed Vault Note` on a single/title hit, so rule 2 has real text to quote.
- **Runtime enforcement** (`PersonaEngine._visible_stream`) cuts the user-visible
  stream at the first `[SEARCH]` / `[SPAWN_WORKER]` tag — a model that "reads out"
  a note it has not been shown yet never reaches the user; the runtime injects the
  real report instead. See
  [2026-09-07 Vault-Grounding Enforcement & Recall Phrasing](../../journal/2026-09/2026-09-07_vault-grounding-enforcement-and-recall-phrasing.md).

---

## 3. Real-World Behavior

### Scenario A: Fact is NOT in memory
> **User:** *"Do you remember what JS framework I need to study in December?"*  
> **Samantha:** *"I don't have that recorded in my memory. What was it so I can log it for you?"*  
> *(No hallucinating "Astro" or making up fake study schedules).*

### Scenario B: Fact WAS captured earlier by Shadow Extractor
> **User:** *"Do you remember what JS framework I need to study in December?"*  
> **Samantha:** *"Yes, I do! You plan to study **Svelte** (along with Rust) in December 2026 for the new web engine."*  
> *(100% accurate, strictly grounded in `profiles/samantha_memory.md`).*
