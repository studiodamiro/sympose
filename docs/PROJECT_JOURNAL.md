---
entry: 2026-08-24
created: 2026-08-24 14:38
type: index
project: sympose
tags:
  - index
  - sympose/master-journal
---

# Sympose Master Journal Index

> **Project:** Sympose Multi-Model Agent Hub  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  

This master document serves as the top-level index and Table of Contents.  
**Daily logs are kept in dedicated individual files inside [`docs/journal/`](file:///Users/damiro/Development/sympose/docs/journal) under `YYYY-MM-DD_topic_slug.md`.**

---

## Daily Engineering Entries

| Date | Topic / Focus | Status | Daily Log File |
| :--- | :--- | :--- | :--- |
| **2026-08-24** | Foundation Review, Phase 1A/1B Delivery & ADR-001 through ADR-004 | Complete | [`2026-08-24_foundation_review.md`](file:///Users/damiro/Development/sympose/docs/journal/2026-08-24_foundation_review.md) |

---

## Architectural Decision Records (ADR Index)

* **[ADR-001 (2026-08-24): Core Runtime Resilience](file:///Users/damiro/Development/sympose/docs/journal/2026-08-24_foundation_review.md#adr-001-core-runtime--execution-resilience):**
  * *ADR-001.1:* Smart Sliding Window (15–20 Turns) vs. 6-Turn Truncation
  * *ADR-001.2:* Defensive File Access for Obsidian Vault
  * *ADR-001.3:* Local Ollama Offline Resilience
  * *ADR-001.4:* Phased 4-Step Build Sequence
  * *ADR-001.5:* Zero-Latency Explicit API Key Resolution
* **[ADR-002 (2026-08-24): Master Vault Domain Sandboxing](file:///Users/damiro/Development/sympose/docs/journal/2026-08-24_foundation_review.md#adr-002-master-vault-domain-sandboxing--access-control):**
  * Strict folder-level sandboxing (`/General`, `/Engineering`, `/Personal`) per agent profile.
  * Hard security boundary (`is_safe_path()`) preventing cloud models from inspecting private notes.
* **[ADR-003 (2026-08-24): Pluggable Multi-Tier Vault Search Architecture](file:///Users/damiro/Development/sympose/docs/journal/2026-08-24_foundation_review.md#adr-003-pluggable-multi-tier-vault-search-architecture):**
  * Configurable search mode: `direct` (Pure Python), `sqlite_fts` (Ranked BM25), `semantic` (Local Vector Embeddings).
* **[ADR-004 (2026-08-24): Industry-Standard Modular Package Architecture](file:///Users/damiro/Development/sympose/docs/journal/2026-08-24_foundation_review.md#adr-004-industry-standard-modular-package-architecture):**
  * Segregated monolithic runtime into a clean `sympose/` package (`config`, `profiles`, `vault`, `engine`, `cli`), reducing `app.py` to a lean 35-line entry point.

---

## Technical Guides
* **[Latency & Performance Tuning Guide](file:///Users/damiro/Development/sympose/docs/LATENCY_TUNING_GUIDE.md):** Complete catalog of knobs, timeouts, context windows, and model configurations governing sub-second SLA.
