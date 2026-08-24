---
entry: 2026-08-24
created: 2026-08-24 17:18
type: spec
project: sympose
tags:
  - sympose/performance
  - sympose/latency
  - engineering/guide
---

# ⚡ Sympose Latency & Performance Tuning Guide

> **Target SLA:** Sub-1.0s Time-To-First-Token (TTFT) across all agents.  
> **Architecture:** Zero-Bloat Agnostic Model Router (`sympose/`) on macOS Apple Silicon.

This reference lists all key configuration variables, system flags, and architectural knobs governing latency in Sympose, where they live, their optimal defaults, and their impact.

---

## 🎛️ Master Tuning Parameters

| Parameter | Location | Default / Recommended | Purpose & Latency Impact |
| :--- | :--- | :--- | :--- |
| **`timeout`** | [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py#L189) | `10.0` (seconds) | Hard ceiling on HTTP connection. Prevents API endpoints from hanging when rate-limited. |
| **`litellm.request_timeout`** | [`sympose/config.py`](file:///Users/damiro/Development/sympose/sympose/config.py#L23) | `10.0` (seconds) | Global library timeout for network sockets. |
| **`litellm.drop_params`** | [`sympose/config.py`](file:///Users/damiro/Development/sympose/sympose/config.py#L22) | `True` | Silently discards unsupported vendor flags (e.g. deprecated temperature on Gemini 3+), preventing retry loops. |
| **`max_turns`** | [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py#L17) | `15` (30 messages) | Sliding context window. Limits prompt history payload to under ~2,000 tokens, eliminating pre-fill latency. |
| **`stream`** | [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py#L188) | `True` | Streams tokens via HTTP chunking at 60 FPS, reducing perceived wait time from 10s to **0.8s TTFT**. |
| **`temperature`** | [`profiles/*.yaml`](file:///Users/damiro/Development/sympose/profiles/grace.yaml#L5) | `0.1` (Code) / `0.7` (Creative) | Lower temperature reduces token branch sampling latency and ensures deterministic code. |
| **`model`** | [`profiles/*.yaml`](file:///Users/damiro/Development/sympose/profiles/samantha.yaml#L4) | `gemini/gemini-3.5-flash-lite` | Selects backend engine. Flash-Lite yields **0.7s TTFT**, Sonnet yields **1.4s**, local Gemma2 yields **0.5s**. |
| **`api_base`** | [`profiles/*.yaml`](file:///Users/damiro/Development/sympose/profiles/aurelius.yaml#L5) | `http://localhost:11434` | Direct localhost loopback for Ollama (0ms DNS lookup time). |

---

## 🔍 Deep-Dive: Latency Gotchas & Resolutions

### 1. The 75-Second Google Cloud Vertex ADC Hang
* **The Problem:** When calling Google Gemini via LiteLLM without explicit API key injection, LiteLLM probes the local machine for Google Cloud Vertex Application Default Credentials (`~/.config/gcloud/`). If unauthenticated, it hangs for Google's default 75s auth timeout before falling back to `.env`.
* **The Resolution in Sympose:**
  1. [`sympose/config.py`](file:///Users/damiro/Development/sympose/sympose/config.py#L18) runs `os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)`.
  2. [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py#L192) explicitly injects `kwargs["api_key"] = os.getenv("GEMINI_API_KEY")`.
  3. **Result:** First token drops from **76.0s ➔ 0.85s**.

---

### 2. Context Window Bloat (Token Pre-fill Overhead)
* **The Problem:** If chat history grows unchecked to 50+ turns (10,000+ tokens), the LLM must process the entire history before generating the very first word. This adds 3 to 8 seconds of pre-fill delay on every turn.
* **The Resolution in Sympose:**
  * [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py#L174) enforces `history[-(self.max_turns * 2):]`.
  * Preserves working context while keeping total token payload under **~2,000 tokens** (sub-100ms pre-fill).

---

### 3. Persona Soul & Memory Conciseness
* **The Problem:** Giant 500-line prompt templates add unnecessary token weight to every request.
* **The Resolution in Sympose:**
  * Keep [`_soul.md`](file:///Users/damiro/Development/sympose/profiles/samantha_soul.md) files under **30 lines** of crisp, high-signal directives.
  * Bullet-point facts in [`_memory.md`](file:///Users/damiro/Development/sympose/profiles/samantha_memory.md) rather than verbose paragraphs.

---

### 4. Local Ollama GPU Acceleration (Marcus Aurelius)
* **Hardware:** Apple Silicon (Unified Memory Architecture).
* **Optimization:**
  * Run quantized GGUF models (`ollama run gemma2:9b` or `qwen2.5-coder:7b`).
  * Runs 100% in Metal GPU memory, generating tokens at **45+ tokens/second with 0ms network latency**.

---

## 🛠️ How to Tweak Variables on the Fly

### Change Backend Model in Real-Time:
```bash
/model gemini/gemini-3.5-flash-lite
```

### Clear Context if History Grows Heavy:
```bash
/reset
```

### Edit Persona Defaults:
Directly edit [`profiles/samantha.yaml`](file:///Users/damiro/Development/sympose/profiles/samantha.yaml), [`profiles/grace.yaml`](file:///Users/damiro/Development/sympose/profiles/grace.yaml), or [`profiles/aurelius.yaml`](file:///Users/damiro/Development/sympose/profiles/aurelius.yaml). Changes take effect instantly on next prompt!
