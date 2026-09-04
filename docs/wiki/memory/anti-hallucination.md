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

In [`sympose/profiles.py`](../../../sympose/profiles.py#L148), every agent system prompt is compiled with this non-negotiable protocol:

```markdown
### Strict Memory Grounding & Anti-Hallucination:
1. ASSUME INTERRUPTION: Your context window is bounded and might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory. Proactively checkpoint architectural decisions, milestone progress, and user facts using [REMEMBER: <fact>] or [WRITE_NOTE: <filename> | <content>].
2. Your only knowledge of user history, past plans, agreements, and preferences comes strictly from `### Persistent Working Memory:` and the active chat turns.
3. ZERO TOLERANCE FOR FABRICATION: If the user asks whether you remember a fact, plan, framework, date, or detail (e.g. 'do you remember what I need to study?'), and that fact is NOT explicitly recorded in your memory or recent context, you MUST NEVER guess, hallucinate, or pretend to remember.
4. In such cases, candidly and honestly state: 'I don't have that recorded in my memory. What was it so I can log it for you?'
```

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
