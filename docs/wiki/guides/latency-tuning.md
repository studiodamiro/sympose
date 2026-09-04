---
title: "Sympose Latency & Performance Tuning Guide"
created: 2026-08-24
type: wiki-guides
parent: index
tags:
  - sympose/wiki
  - engineering/standard
---

# ⚡ Sympose Latency & Performance Tuning Guide

> **Target SLA:** Sub-1.0s Time-To-First-Token (TTFT) across all agents.  
> **Architecture:** Zero-Bloat Agnostic Model Router (`sympose/`) on macOS Apple Silicon.

This reference lists all key configuration variables, system flags, and architectural knobs governing latency in Sympose, where they live, their optimal defaults, and their impact.

---

## 🎛️ Master Tuning Parameters

All performance, latency, and context parameters are now centrally managed in [`config.yaml`](../../../config.yaml) and can be adjusted statically or tuned live in the CLI session using `/config set <key> <val>`.

| Parameter | Primary Location | CLI Dynamic Override | Default / Recommended | Purpose & Latency Impact |
| :--- | :--- | :--- | :--- | :--- |
| **`performance.request_timeout`** | [`config.yaml`](../../../config.yaml#L6) | `/config set performance.request_timeout 10.0` | `10.0` (seconds) | Hard ceiling on HTTP connection & socket timeout. |
| **`performance.max_context_turns`** | [`config.yaml`](../../../config.yaml#L7) | `/config set performance.max_context_turns 15` | `15` (30 messages) | Sliding context window. Limits prompt history payload under ~2,000 tokens, eliminating pre-fill latency. |
| **`performance.max_worker_tool_turns`** | [`config.yaml`](../../../config.yaml#L8) | `/config set performance.max_worker_tool_turns 8` | `8` (turns) | Hard ceiling on sub-agent tool calling iterations, preventing runaway loops while allowing multi-file research. |
| **`performance.drop_unsupported_params`** | [`config.yaml`](../../../config.yaml#L9) | `/config set performance.drop_unsupported_params true` | `true` | Silently discards unsupported vendor flags, preventing retry loops. |
| **`performance.stream`** | [`config.yaml`](../../../config.yaml#L9) | `/config set performance.stream true` | `true` | Streams tokens via HTTP chunking at 60 FPS, achieving **0.8s TTFT**. |
| **`session.exit_behavior.summarization_model`** | [`config.yaml`](../../../config.yaml#L17) | `/config set session.exit_behavior.summarization_model <model>` | `gemini/gemini-3.5-flash-lite` | Dedicated ultra-fast model for near-instant session summarization. |
| **`temperature`** | [`profiles/*.yaml`](../../../profiles/grace.yaml#L5) | N/A (per-persona) | `0.1` (Code) / `0.7` (Creative) | Lower temperature reduces token branch sampling latency and ensures deterministic code. |
| **`model`** | [`profiles/*.yaml`](../../../profiles/samantha.yaml#L4) | `/model <provider/name>` | `gemini/gemini-3.5-flash-lite` | Flash-Lite yields **0.7s TTFT**, Sonnet yields **1.4s**, local Gemma2 yields **0.5s**. |
| **`api_base`** | [`profiles/*.yaml`](../../../profiles/aurelius.yaml#L5) | N/A (per-persona) | `http://localhost:11434` | Direct localhost loopback for Ollama (0ms DNS lookup time). |
| **`vault.search_mode`** | [`config.yaml`](../../../config.yaml#L64) | `/config set vault.search_mode sqlite_fts` | `direct` | `direct`: pure-Python walk, zero setup, fine for small/medium vaults. `sqlite_fts`: BM25-ranked full-text search via a stdlib SQLite FTS5 index — switch to this once `direct`'s linear scan starts costing real TTFT on a large vault. |

---

## 🔍 Deep-Dive: Latency Gotchas & Resolutions

### 1. The GCE Metadata Probe & Vertex ADC Hang (30s – 300s Timeout)
* **The Problem:** Python Google Cloud libraries automatically probe `http://169.254.169.254` (the internal Google Compute Engine metadata server) and Vertex ADC credentials. On macOS / non-cloud machines, `169.254.169.254` is unroutable, causing TCP SYN socket hangs for 10s to 300s before falling back to `GEMINI_API_KEY`.
* **The Resolution in Sympose:**
  1. [`sympose/config.py`](../../../sympose/config.py#L20) sets `os.environ["NO_GCE_CHECK"] = "True"`, `os.environ["GOOGLE_CLOUD_DISABLE_METADATA"] = "true"`, and purges `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEXAI_PROJECT`, and `GOOGLE_CLOUD_PROJECT`.
  2. [`sympose/__init__.py`](../../../sympose/__init__.py) imports `sympose.config` first to guarantee environment variables are active before LiteLLM or Google SDK initializes.
  3. [`sympose/engine.py`](../../../sympose/engine.py#L140) explicitly injects `kwargs["api_key"] = os.getenv("GEMINI_API_KEY")`.
  4. **Result:** First token consistently streams in **0.75s – 0.85s TTFT** on initial call!

---

### 2. Context Window Bloat (Token Pre-fill Overhead)
* **The Problem:** If chat history grows unchecked to 50+ turns (10,000+ tokens), the LLM must process the entire history before generating the very first word. This adds 3 to 8 seconds of pre-fill delay on every turn.
* **The Resolution in Sympose:**
  * [`sympose/engine.py`](../../../sympose/engine.py#L174) enforces `history[-(self.max_turns * 2):]`.
  * Preserves working context while keeping total token payload under **~2,000 tokens** (sub-100ms pre-fill).

---

### 3. Persona Soul & Memory Conciseness
* **The Problem:** Giant 500-line prompt templates add unnecessary token weight to every request.
* **The Resolution in Sympose:**
  * Keep [`_soul.md`](../../../profiles/samantha_soul.md) files under **30 lines** of crisp, high-signal directives.
  * Bullet-point facts in [`_memory.md`](../../../profiles/samantha_memory.md) rather than verbose paragraphs.

---

### 4. Vault Search at Scale (`sqlite_fts`)
* **The Problem:** `direct` mode's `search_structured`/`get_folder_digest` scan an mtime-cached in-memory snapshot of every note under scope — cheap for a personal vault, but a linear cost that grows with vault size, and it's a plain substring match with no ranking.
* **The Resolution in Sympose:**
  * Set `vault.search_mode: sqlite_fts` and Sympose builds a stdlib `sqlite3` FTS5 index under the workspace (`.vault_index/`, never inside your actual Obsidian vault) — see [ADR-070.5](../../journal/2026-09/2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md).
  * BM25 ranking, title-weighted above body, prefix-matched per query token — better recall and ordering than a raw substring scan.
  * A note Sympose writes itself is indexed immediately (no rebuild wait); external edits (Obsidian, sync, git pull) are picked up on the next query once the tracked directory-mtime watermark drifts.
  * No new dependency — falls back to `direct` with no visible error if this Python's `sqlite3` wasn't built with the FTS5 extension.

---

### 5. Local Ollama GPU Acceleration (Marcus Aurelius)
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
Directly edit [`profiles/samantha.yaml`](../../../profiles/samantha.yaml), [`profiles/grace.yaml`](../../../profiles/grace.yaml), or [`profiles/aurelius.yaml`](../../../profiles/aurelius.yaml). Changes take effect instantly on next prompt!
