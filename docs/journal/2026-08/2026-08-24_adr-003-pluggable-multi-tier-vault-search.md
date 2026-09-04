---
title: "ADR-003 — Pluggable Multi-Tier Vault Search Architecture"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-003 — Pluggable Multi-Tier Vault Search Architecture

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Vault retrieval needs to scale from a trivial substring scan to ranked and
semantic search without committing the whole project to a heavyweight index on
day one.

## Decision

Implement search as pluggable modes selected by configuration, in increasing
order of cost and capability:

1. `direct` — pure-Python path and substring matching.
2. `sqlite_fts` — ranked BM25 full-text search over an SQLite FTS index.
3. `semantic` — local vector embeddings.

`direct` is the default; the heavier tiers are opt-in.

## Consequences

**Positive**

- The zero-dependency `direct` mode ships first and covers most queries.
- Higher tiers are additive and do not change the calling contract.

**Negative / costs**

- Only `direct` is implemented at decision time; `sqlite_fts` and `semantic`
  remain design intent. Later retrieval work
  ([ADR-022](./2026-08-25_adr-022-local-first-hierarchical-retrieval.md),
  [ADR-044](./2026-08-27_adr-044-in-memory-inverted-index-backlink-engine.md))
  favours in-memory structures over the SQLite tier.

## Alternatives rejected

- **Committing to a single ranked/semantic index up front.** Rejected: adds an
  index build, a dependency, and maintenance before the need is proven; the
  tiered contract lets `direct` ship immediately.
