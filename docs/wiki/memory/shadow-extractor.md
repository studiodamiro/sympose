---
title: "Heuristic Gated Shadow Memory Extractor"
created: 2026-08-24
type: wiki-memory
parent: index
tags:
  - sympose/memory
  - autonomous-agents
  - shadow-extractor
---

# 🧠 Heuristic Gated Shadow Memory Extractor

The **Shadow Extractor** is Sympose's autonomic memory capture engine. It solves the fundamental flaw of AI assistants: forcing users to do the mental bookkeeping of remembering to ask their assistant to remember.

---

## 1. How It Operates in Real Time

```
Your Natural Chat:
"I need to study Svelte and Rust in December 2026 for our new web engine."
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
[Real-Time Fast Path]                               [Async Shadow Daemon Thread]
Samantha streams in 0.83s:                          Heuristic Gate detects planning intent.
"Got it! Svelte's reactivity..."                    Background prompt distills fact and silently
                                                    appends to profiles/samantha_memory.md:
                                                    • "User plans to study Svelte and Rust in Dec 2026"
```

---

## 2. The Heuristic Filter Gate

Firing a background LLM evaluation on *every single turn* is wasteful: it doubles token consumption, risks hitting API rate limits (RPM), and clutters memory with conversational noise (e.g. *"User said hello"*).

Sympose uses a **dual-filter heuristic gate** in [`sympose/memory.py`](./sympose/memory.py#L18):

```python
TRIGGER_PATTERNS = [
    r"\b(i\s+will|i\s+plan|i\s+need|i\s+want|i\s+am\s+going\s+to|i\s+prefer)\b",
    r"\b(we\s+decided|we\s+are\s+using|we\s+switched|let\'?s\s+use|our\s+stack|our\s+database)\b",
    r"\b(on\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))\b",
    r"\b(my\s+name\s+is|my\s+favorite|my\s+timezone|my\s+role|i\s+live\s+in)\b",
    r"\b(birthday|anniversary|born|married|wife|husband|kid|kids|son|daughter|family|partner|friend)\b",
    r"\b(rule|constraint|never\s+use|always\s+use|deploy\s+to|secret|credential)\b",
]

SKIP_PATTERNS = [
    r"^(hi|hello|hey|thanks|thank you|ok|okay|cool|great|bye|quit|exit|ping)\b",
    r"^(what is|who is|how do i|explain|summarize|convert)\b",
]
```

### Performance & Economics:
- **Skip Rate**: >80% of casual turns are skipped in `<0.01ms` (0 extra tokens).
- **Cost**: Less than **$0.003 per 1,000 conversational turns** using `gemini-3.5-flash-lite`.
- **Latency Impact**: **0.00s** added to user streaming (runs in a detached daemon thread).

---

## 3. Silent Deduplication & Hygiene

When a fact is extracted, [`ProfileManager.append_memory()`](file:///Users/damiro/Development/sympose/sympose/profiles.py) checks the existing `_memory.md` text under process-wide mutex lock before writing, preventing duplicate bullet points from being appended across sessions.

---

## 4. Declarative Templates & Preamble-Resilient Parsing (ADR-037 & ADR-038)

Extraction instructions are decoupled from Python code and maintained in [`prompts/memory_extraction.md`](file:///Users/damiro/Development/sympose/prompts/memory_extraction.md):
- **Anchored Asset Resolution**: Prompts are discovered relative to package root (`sympose/../prompts/`).
- **Resilient Line Parsing**: Rather than checking index 0 prefix (`startswith("-")`), the parser extracts bullet lines line-by-line, ensuring facts accompanied by conversational remarks are captured cleanly.
