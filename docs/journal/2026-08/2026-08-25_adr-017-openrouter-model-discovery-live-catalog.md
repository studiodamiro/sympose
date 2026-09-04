---
title: "ADR-017 — Dynamic OpenRouter Model Discovery & Live Catalog Search"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-017 — Dynamic OpenRouter Model Discovery & Live Catalog Search (`sympose/models.py`)

- **Status:** Accepted — the cache-file path bug is fixed by
  [ADR-049](./2026-08-29_adr-049-code-fence-action-tag-parsing.md)
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

OpenRouter adds cutting-edge models weekly, so static lists go stale fast — but
a network call on every keystroke would hurt CLI latency.

## Decision

- `sympose/models.py` (`ModelCatalog`) with a 24-hour local disk cache
  (`~/.sympose_models_cache.json`).
- `/model find <keyword>` (alias `/model search`) queries the cache instantly,
  showing context lengths and pricing.
- `/model refresh` force-syncs the latest catalog from OpenRouter's API on
  demand.
- `sympose/completer.py` gains Readline tab completion for `/model`,
  `/model find <term>`, and `openrouter/*` slugs.

## Consequences

**Positive**

- Fresh model discovery with zero latency on the common path.
- No hand-maintained model dictionary.

**Negative / costs**

- A 24-hour cache can be up to a day stale until `/model refresh` is run.

## Alternatives rejected

- **A hardcoded / hand-maintained model list.** Rejected: stale within a week
  and a standing maintenance burden.
- **Live network lookup on every keystroke.** Rejected: unacceptable CLI input
  latency.
