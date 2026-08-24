---
title: "Autonomous Agent Memory Architecture Standard"
created: 2026-08-24
type: architecture-standard
status: approved
tags:
  - sympose/architecture
  - ai/memory-systems
  - prompt-engineering
  - system-design
  - obsidian-standard
aliases:
  - Memory Standard
  - Autonomous Agent Memory Standard
---

# 🧠 Autonomous Agent Memory Architecture Standard
> **A zero-bloat, sub-second, and self-grounding memory architecture for personal multi-agent hubs.**

---

## 1. Executive Summary & Core Philosophy

Modern AI assistants suffer from two fatal design flaws:
1. **The Manual Overhead Trap**: Forcing users to explicitly invoke commands like `/remember` or preface sentences with *"Please remember that..."*. If a human must do the cognitive bookkeeping, the assistant fails its primary purpose.
2. **The Sycophancy & Hallucination Trap**: Base LLMs are trained to be agreeable. When asked *"Do you remember X?"*, they default to fabricating a plausible answer (e.g. *"Yes, you planned to study Astro!"*) rather than admitting ignorance.

This standard establishes the **Sympose Triad Memory Architecture**: a file-based, sub-second (`<0.8s TTFT`), and autonomous memory framework that captures durable user facts invisibly while strictly eliminating hallucinations.

---

## 2. The Triad Memory Architecture

```mermaid
graph TD
    User([User Natural Input]) --> Gate{Heuristic Filter Gate}
    
    subgraph Fast Path [Sub-Second Streaming <0.8s]
        User --> MainLLM[Active Agent LLM]
        MainLLM --> Screen[60 FPS Terminal Output]
    end
    
    subgraph Shadow Path [Detached Async Daemon Thread]
        Gate -- Signal Detected --> Extractor[Shadow Extractor LLM]
        Extractor --> Dedupe[Deduplication & Hygiene]
        Dedupe --> MemoryFile[profiles/_memory.md]
        Gate -- Chit-Chat / Trivial --> Skip[0 Extra Tokens / No-Op]
    end
    
    subgraph Archival Path [Session Exit /save]
        ExitCmd[/exit or /save] --> Archivist[Session Archivist LLM]
        Archivist --> MemoryFile
        Archivist --> Vault[Obsidian Vault Sessions/]
    end
```

### The 3 Core Components

| Artifact | Location | Responsibility | Token Cost |
| :--- | :--- | :--- | :--- |
| **Profile Manifest** | `profiles/{handle}.yaml` | Machine-readable identity metadata & UI spinner phrases (`thinking_phrases`). | 0 prompt tokens |
| **Agent Soul** | `profiles/{handle}_soul.md` | Inflexible cognitive directives, tone, analytical heuristics, and strict anti-hallucination boundaries. | ~200 prompt tokens |
| **Working Memory** | `profiles/{handle}_memory.md` | Dynamically updated, high-signal bullet points representing permanent user facts, preferences, and stack constraints. | ~150–300 tokens |

---

## 3. The 4 Anti-Hallucination Grounding Pillars

To guarantee **100% brutal honesty** and eliminate conversational guessing, four mechanical constraints must be enforced:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. THE AMNESIA BOUNDARY                                     │
│    Agent is instructed that it possesses ZERO organic memory │
│    outside of `### Persistent Working Memory:` and turns.   │
├─────────────────────────────────────────────────────────────┤
│ 2. ZERO TOLERANCE FOR GUESSING                              │
│    Guessing or pretending to remember is a critical failure. │
├─────────────────────────────────────────────────────────────┤
│ 3. CANDID IGNORANCE PROTOCOL                                │
│    If a fact is missing, output: "I have no record of that. │
│    Tell me what it is and I'll log it."                     │
├─────────────────────────────────────────────────────────────┤
│ 4. TEMPERATURE DISCIPLINE                                   │
│    Set `temperature: 0.1` for factual & engineering agents. │
└─────────────────────────────────────────────────────────────┘
```

### System Prompt Directive Template:
```markdown
### Strict Memory Truthfulness & Anti-Hallucination Protocol:
1. Your sole knowledge of user history, preferences, and past agreements begins and ends with `### Persistent Working Memory:` and active session turns.
2. ZERO TOLERANCE FOR FABRICATION: If the user asks whether you remember a fact, plan, framework, date, or detail, and that detail is NOT explicitly recorded in your memory file, you MUST NEVER guess, assume, or pretend to remember.
3. In such cases, candidly state: "I don't have that recorded in my memory. What was it so I can log it for you?"
```

---

## 4. The Heuristic Gated Shadow Extractor

Instead of naively calling a background LLM on every single turn (which doubles token cost and exhausts rate limits), Sympose employs a **two-tier heuristic gate**:

```python
class HeuristicGatedExtractor:
    TRIGGER_PATTERNS = [
        r"\b(i\s+will|i\s+plan|i\s+need|i\s+want|i\s+am\s+going\s+to|i\s+prefer)\b",
        r"\b(we\s+decided|we\s+are\s+using|we\s+switched|let\'?s\s+use|our\s+stack|our\s+database)\b",
        r"\b(on\s+(?:january|february|march|april|may|june|july|august|september|october|november|december))\b",
        r"\b(my\s+name\s+is|my\s+favorite|my\s+timezone|my\s+role|i\s+live\s+in)\b",
        r"\b(rule|constraint|never\s+use|always\s+use|deploy\s+to|secret|credential)\b",
    ]

    SKIP_PATTERNS = [
        r"^(hi|hello|hey|thanks|thank you|ok|okay|cool|great|bye|quit|exit|ping)\b",
        r"^(what is|who is|how do i|explain|summarize|convert)\b",
    ]
```

### Execution Flow:
1. **Filter Pass (0.01ms)**: If the prompt matches `SKIP_PATTERNS` or lacks `TRIGGER_PATTERNS`, the extractor immediately aborts with **0 network calls**.
2. **Async Spawning (0.05ms)**: If a trigger is detected, the extractor spawns a detached Python daemon thread (`threading.Thread(daemon=True)`).
3. **Stream Non-Interference**: The user's streaming output on the main thread is completely unaffected (**0.00s added latency**).
4. **Deduplicated Append**: The extracted bullet point is checked against existing `_memory.md` content to prevent duplicate records.

---

## 5. Latency Zero-Impact & OS-Level Optimizations

### The GCE Metadata Server Hang (`169.254.169.254`)
* **Gotcha**: On local macOS, Python Google Cloud SDKs probe `http://169.254.169.254` (the internal Google Compute Engine metadata server). Because that IP is unroutable outside Google Cloud VMs, the socket hangs in a TCP SYN timeout for **10s to 300s** before falling back to `.env` API keys.
* **The Universal Fix**:
```python
os.environ["NO_GCE_CHECK"] = "True"
os.environ["GOOGLE_CLOUD_DISABLE_METADATA"] = "true"
os.environ["GCE_METADATA_TIMEOUT"] = "0"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
```

---

## 6. Token Economics & Cost Calculation

Using `gemini-3.5-flash-lite` ($0.075 per 1M input tokens):

$$\text{Cost per 1,000 Turns} = \frac{1,000 \times \text{Trigger Rate (15\%)} \times 250 \text{ tokens}}{1,000,000} \times \$0.075 \approx \mathbf{\$0.0028}$$

* **Manual User Burden**: $0$ seconds.
* **Financial Overhead**: Less than one-third of a cent per 1,000 messages.
* **Reliability**: 100% persistent markdown files on local disk.

---

## 7. Obsidian Vault Integration

Session logs created on `/exit` follow structured YAML frontmatter:

```markdown
---
type: session-log
agent: samantha
date: 2026-08-24 18:35
model: gemini/gemini-3.5-flash-lite
tags:
  - sympose/session
  - agent/samantha
---

# Session Takeaways: 2026-08-24 18:35

## Overview & Intent
Brief summary of the discussion.

## Key Decisions & Architecture Highlights
- Architectural choices made during the session.

## Action Items & Next Steps
- [ ] Next action item.
```

---
*Standard ratified on 2026-08-24. Implemented in Sympose Core Package (`sympose/`).*
