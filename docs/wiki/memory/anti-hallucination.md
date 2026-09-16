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
│    The persona is instructed that it has zero organic memory│
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
│    Set `temperature: 0.1` for factual & engineering personas.│
├─────────────────────────────────────────────────────────────┤
│ 5. ASSUME INTERRUPTION (Write-Through State Persistence)    │
│    Context windows are bounded & volatile. Proactively     │
│    checkpoint architectural decisions & facts to disk.      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. The Universal System Prompt Grounding Directive

Every persona system prompt compiled by [`ProfileManager.build_system_prompt`](../../../sympose/profiles.py) carries the **Grounding & Anti-Hallucination** block from [`sympose/prompts/workspace_rules.md`](../../../sympose/prompts/workspace_rules.md) (packaged; the user-editable copy at `~/.sympose/prompts/workspace_rules.md` wins when present). It is non-negotiable:

```markdown
### Grounding & Anti-Hallucination
The vault and the user's history are a document you read, never one you remember.
Every claim about them is a verbatim quote or it is nothing.

1. Your knowledge of the user is exactly {{sources}} plus the active turns — nothing else.
2. State a fact about a note only from a payload given this turn — a
   `### Ground-Truth Sandboxed Vault Note`, `### Ground-Truth Vault Search Results`,
   or a Sub-Agent Report. Quote paths, dates, names, and wording exactly.
   Never reconstruct a note from the topic, the conversation, or what sounds plausible.
3. No payload → don't guess. Not shown the note: say so and emit
   `[SPAWN_SUB_AGENT: vault_read | <subject>]`. Retrieval empty: "I have no record
   of that in your vault." Never use `[SEARCH]` (web) for the user's own notes.
4. Emit `[SEARCH]` / `[SPAWN_SUB_AGENT]`, then stop — you have not seen the result yet.
```

Three layers back the prompt up so it holds on a weak/abliterated local model,
not only a strong cloud one:

- **Retrieval** (`VaultManager.resolve_turn_context` / `_recall_hit`) prefers to
  inject the **full verbatim note body** as the pre-turn `### Ground-Truth
  Sandboxed Vault Note` on a single/title hit, so rule 2 has real text to quote.
- **Runtime enforcement** (`PersonaEngine._visible_stream`) cuts the user-visible
  stream at the first `[SEARCH]` / `[SPAWN_SUB_AGENT]` tag — a model that "reads out"
  a note it has not been shown yet never reaches the user; the runtime injects the
  real report instead. See
  [2026-09-07 Vault-Grounding Enforcement & Recall Phrasing](../../journal/2026-09/2026-09-07_vault-grounding-enforcement-and-recall-phrasing.md).
- **Post-hoc structural backstop** — the prompt rule is an instruction, not a
  guarantee; these checks run *after* the model answers and don't trust its
  compliance. See §3 below.

---

## 3. Deterministic Structural Backstops

The two layers above assume the model follows rule 2. It sometimes doesn't —
so every reply that could contain a vault claim is checked deterministically
before the user sees it, on both paths a persona can answer through. None of
these add a second model call (round-trip-frugal by design): they compare the
reply's own text against what was actually, verifiably handed to or retrieved
by the model this turn, and substitute the real thing on a mismatch.

**Primary persona path** (`sympose/engine.py`, given a pre-fetched `vault_ctx`):
| Check | Catches |
| --- | --- |
| `_vault_ctx_citation_mismatch` | Reply names a vault-note-shaped path that isn't among the real ones it was handed |
| `_vault_ctx_title_missing` | A real note *was* handed over, but the reply never references it at all |

**Sub-agent path** (`sympose/sub_agents.py`, which fetches its own content via tools instead of a pre-fetched `vault_ctx`):
| Check | Catches |
| --- | --- |
| `_content_unread` | Reply names/quotes a specific note that was never actually retrieved via a successful tool call this turn |
| `_content_unsupported` | Reply makes a substantive claim sharing no verbatim run of words with anything externally retrieved this turn, despite a retrieval attempt having been made |

Both sub-agent checks were built and live-verified (real `ollama/gemma4:e4b`
and `gemini/gemini-3.6-flash` calls, not just mocked tests) in
[2026-09-17 Sub-Agent Guard Against Unsupported Synthesis](../../journal/2026-09/2026-09-17_sub-agent-unsupported-synthesis-guard.md),
which also closed a related loophole: a successful tool call whose "result"
is just the model's own invented text laundered through a real shell command
(e.g. `run_command(echo "I found...")`) doesn't count as retrieved evidence —
only externally-sourced tool output does.

What these checks explicitly don't cover: a model abandoning the task
entirely (calling a tool that doesn't exist, answering something unrelated)
isn't a vault-content claim to verify, so no grounding check catches it — see
["The real bottleneck is local-model reliability"](../reference/vault-agent-capabilities.md#the-real-bottleneck-is-local-model-reliability-not-tool-availability).

---

## 4. Real-World Behavior

### Scenario A: Fact is NOT in memory
> **User:** *"Do you remember what JS framework I need to study in December?"*  
> **Samantha:** *"I don't have that recorded in my memory. What was it so I can log it for you?"*  
> *(No hallucinating "Astro" or making up fake study schedules).*

### Scenario B: Fact WAS captured earlier by Shadow Extractor
> **User:** *"Do you remember what JS framework I need to study in December?"*  
> **Samantha:** *"Yes, I do! You plan to study **Svelte** (along with Rust) in December 2026 for the new web engine."*  
> *(100% accurate, strictly grounded in `profiles/samantha_memory.md`).*
