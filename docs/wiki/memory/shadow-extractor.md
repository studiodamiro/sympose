---
title: "Heuristic Gated Shadow Memory Extractor"
created: 2026-08-24
type: wiki-memory
parent: index
tags:
  - sympose/memory
  - autonomous-personas
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

Sympose uses a **dual-filter heuristic gate** in [`sympose/memory.py`](../../../sympose/memory.py#L28):

```python
TRIGGER_PATTERNS = [
    r"\b(?:my\s+name\s+is|i\s+am|i'm|call\s+me)\b",
    r"\b(?:i\s+live\s+in|my\s+timezone\s+is|i\s+work\s+at|my\s+job\s+is|i\s+am\s+a)\b",
    r"\b(?:i\s+prefer|i\s+like|i\s+dislike|i\s+hate|always\s+use|never\s+use|my\s+favorite)\b",
    r"\b(?:remember\s+that|keep\s+in\s+mind|don't\s+forget|note\s+that|save\s+this)\b",
    r"\b(?:we\s+decided|the\s+architecture\s+is|we\s+are\s+building|the\s+stack\s+is)\b",
    r"\b(?:my\s+goal\s+is|the\s+deadline\s+is|we\s+need\s+to\s+ship)\b",
]

SKIP_PATTERNS = [
    r"^(?:hi|hello|hey|yo|thanks|thank\s+you|ok|okay|cool|nice|yes|no|yep|nope)[\.\!\?]?$",
    r"^(?:clear|reset|delete|help|exit|quit|status|\/switch|\/save|\/clear|\/reset)",
    r"^\[SPAWN_SUB_AGENT:",
]
```

### Performance & Economics:
- **Skip Rate**: >80% of casual turns are skipped in `<0.01ms` (0 extra tokens).
- **Cost**: Less than **$0.003 per 1,000 conversational turns** using `gemini-3.6-flash`.
- **Latency Impact**: **0.00s** added to user streaming (runs in a detached daemon thread).

---

## 3. Prompt-Level Deduplication & Hygiene

`append_memory()` itself does not check for duplicates — it appends under a process-wide mutex lock (safe against concurrent writers) and triggers background compaction once the file crosses `memory.compaction_threshold` bullet lines, but nothing at write time compares a new fact against what's already recorded.

The real dedup happens one step earlier: the extraction prompt itself is shown the persona's *existing* memory file content (`{{existing_memory}}` in [`sympose/prompts/memory_extraction.md`](../../../sympose/prompts/memory_extraction.md)) and told to output `NONE` if the candidate fact is already covered, even if it would be worded differently. `SessionArchivist`'s end-of-session distillation does the same. This was a live bug fix — before it, neither extraction path could see the memory file it was writing into, so the same standing fact (e.g. a coffee preference) got independently re-derived and re-worded across sessions, and `MemoryCompactor`'s later LLM-judgment merge pass didn't reliably recognize differently-phrased restatements as duplicates. Prevention at the source is the primary defense; compaction remains a backstop for whatever still slips through.

---

## 4. Declarative Templates & Preamble-Resilient Parsing (ADR-037 & ADR-038)

Extraction instructions are decoupled from Python code and maintained in [`sympose/prompts/memory_extraction.md`](../../../sympose/prompts/memory_extraction.md):
- **Anchored Asset Resolution**: Templates ship inside the package at `sympose/prompts/` (`package-data`) and are read via `sympose.prompt_assets.load_prompt` — resolved from the package directory, so a wheel / pipx install gets the real file instead of an inline fallback.
- **Resilient Line Parsing**: Rather than checking index 0 prefix (`startswith("-")`), the parser extracts bullet lines line-by-line, ensuring facts accompanied by conversational remarks are captured cleanly.
