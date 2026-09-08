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
| **`performance.request_timeout`** | [`config.yaml`](../../../config.yaml#L2) | `/config set performance.request_timeout 10.0` | `30.0` (seconds) | Hard ceiling on HTTP connection & socket timeout (remote models). |
| **`performance.local_request_timeout`** | [`config.yaml`](../../../config.yaml#L3) | `/config set performance.local_request_timeout 240.0` | `120.0` (seconds) | Separate, higher ceiling for local (`ollama/…`) calls — must exceed the cold first-turn prefill or the turn fails silently. |
| **`performance.local_keep_alive`** | [`config.yaml`](../../../config.yaml#L4) | `/config set performance.local_keep_alive -1` | `None` | Residency hint passed to local calls (`-1` forever, `0` unload now, `"30m"`). `None` defers to the `OLLAMA_KEEP_ALIVE` server env var. Persona YAML `keep_alive` overrides this. |
| **`performance.max_context_turns`** | [`config.yaml`](../../../config.yaml#L8) | `/config set performance.max_context_turns 15` | `15` (30 messages) | Sliding context window. Limits prompt history payload under ~2,000 tokens, eliminating pre-fill latency. |
| **`performance.max_worker_tool_turns`** | [`config.yaml`](../../../config.yaml#L8) | `/config set performance.max_worker_tool_turns 8` | `8` (turns) | Hard ceiling on sub-agent tool calling iterations, preventing runaway loops while allowing multi-file research. |
| **`performance.drop_unsupported_params`** | [`config.yaml`](../../../config.yaml#L9) | `/config set performance.drop_unsupported_params true` | `true` | Silently discards unsupported vendor flags, preventing retry loops. |
| **`performance.stream`** | [`config.yaml`](../../../config.yaml#L9) | `/config set performance.stream true` | `true` | Streams tokens via HTTP chunking at 60 FPS, achieving **0.8s TTFT**. |
| **`session.exit_behavior.summarization_model`** | [`config.yaml`](../../../config.yaml#L17) | `/config set session.exit_behavior.summarization_model <model>` | `""` (empty = the active chat model) | Optional dedicated fast model for near-instant session summarization. |
| **`temperature`** | [`profiles/*.yaml`](../../../profiles/samantha.yaml) | `/persona set @<handle> temperature <n>` | `0.1` (Code) / `0.7` (Creative) | Lower temperature reduces token branch sampling latency and ensures deterministic code. |
| **`model`** | [`profiles/*.yaml`](../../../profiles/samantha.yaml#L4) | `/model <provider/name>` (session) · `/persona set @<handle> model <id>` (persisted) | `gemini/gemini-3.6-flash` | Flash yields sub-second TTFT, Sonnet ~1.4s, local Gemma2 ~0.5s. |
| **`api_base`** / **`keep_alive`** | [`profiles/*.yaml`](../../../profiles/samantha.yaml) | `/persona set @<handle> api_base <url>` · `… keep_alive <hint>` | `http://localhost:11434` | `api_base`: direct localhost loopback for Ollama (0ms DNS). `keep_alive`: per-persona residency override for local backends. |
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

### 6. Prompt-Cache Preservation (Local Models)

Local inference engines (llama.cpp / Ollama) cache the KV state of a **stable
prompt prefix** and only prefill the new suffix each turn. Anything that changes
between turns invalidates the cache from that point onward, forcing a full
re-prefill — on a 14B model at ~80 tok/s a ~5k-token prompt is ~60 s, *every*
turn instead of just the first.

* **No volatile tokens high in the system prompt.** The `{{current_datetime}}`
  substitution is **date-only** (`%Y-%m-%d %A`, no `%H:%M`) for exactly this
  reason — a per-minute timestamp 6 % into the prompt was re-prefilling
  everything after it on every turn (ADR-076 / 2026-09-07 log). Write-time
  stamps (daily notes, session logs) use their own `datetime.now()`.
* **Keep the model resident.** `OLLAMA_KEEP_ALIVE=-1` (server env) stops the
  ~6–10 s reload between turns; the first turn after a gap otherwise pays it on
  top of the prefill. Per-persona override: set `keep_alive` in the persona
  YAML (`-1`, `0`, or a duration like `"30m"`), or `performance.local_keep_alive`
  in `config.yaml` — Sympose passes it through to local (`ollama/…`) calls only.
  On macOS `OLLAMA_KEEP_ALIVE` set via `launchctl setenv` is lost on reboot; to
  persist it, drop a `RunAtLoad` LaunchAgent at
  `~/Library/LaunchAgents/com.sympose.ollama-keepalive.plist` that runs
  `launchctl setenv OLLAMA_KEEP_ALIVE -1`, then `launchctl load` it and restart
  Ollama.
* **Keep the prompt small.** Prefill time is linear in prompt length — the
  ADR-076 skill compression took a persona prompt 5,471 → 2,745 tokens, first
  token ~60 s → ~39 s. `local_request_timeout` (default 120 s) must exceed the
  cold first-turn prefill or the turn fails silently.

---

## 🛠️ How to Tweak Variables on the Fly

### Change Backend Model in Real-Time:
```bash
/model gemini/gemini-3.6-flash
```

### Clear Context if History Grows Heavy:
```bash
/reset
```

### Edit Persona Defaults:
Directly edit [`profiles/samantha.yaml`](../../../profiles/samantha.yaml) (or any persona YAML you have created). Changes take effect instantly on next prompt!
