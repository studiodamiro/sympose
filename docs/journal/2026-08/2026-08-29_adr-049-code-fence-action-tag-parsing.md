---
title: "ADR-049 — Robust Code-Fence Action Tag Parsing & Dynamic Cache Resolution"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-049 — Robust Code-Fence Action Tag Parsing & Dynamic Cache Resolution

- **Status:** Accepted — corrects the code-block masking added by
  [ADR-041](./2026-08-27_adr-041-slack-thread-active-context-isolation.md) and
  the cache-file path from
  [ADR-017](./2026-08-25_adr-017-openrouter-model-discovery-live-catalog.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

(1) When a persona emitted `[CREATE_PERSONA: ...]` inside a fenced code block,
`ActionProcessor.parse_action_tags()` replaced all code blocks with whitespace,
silently dropping the manifest. (2) `sympose/models.py` referenced an undefined
`CACHE_FILE` instead of the local `cache_file = get_cache_file()`.

## Decision

1. **Unmasked action-tag extraction.** Extract tags across the entire response
   text with no destructive code-block masking. Add a regex guard
   (`<(?:handle|manifest|path|content|...)>`) to ignore generic documentation
   template examples. Clean residual empty fences from the display stream.
2. **Cache-file dynamic resolution.** `ModelCatalog.get_cached_models()` writes
   to the resolved `cache_file` path in the active workspace.

## Consequences

**Positive**

- Fenced `[CREATE_PERSONA]` tags execute reliably.
- Model catalog cache writes to the correct workspace path.

**Negative / costs**

- Without masking, documentation examples that look like tags must be excluded by
  the regex guard rather than by fence position — a heuristic that can need
  tuning.

## Alternatives rejected

- **Keeping destructive code-block masking in the parser.** Rejected: it dropped
  legitimate fenced action tags, defeating autonomic persona genesis.
