---
title: "ADR-052 — In-Memory Metadata Caching & Sub-5ms Scalability Standard"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-052 — In-Memory Metadata Caching & Sub-5ms Scalability Standard for Multi-Thousand Note Vaults

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Walking the filesystem and running regex across 5,000–20,000 Markdown files per
web request costs 200–800 ms of disk I/O, breaking the sub-second SLA. Rendering
10,000 DOM nodes in the browser drops frame rates to ~5 FPS.

## Decision

- **Tiered data pipeline.** Tier 1: `/api/vault/graph` and `/api/vault/cloud`
  return high-density node metadata compiled from Python RAM in < 2 ms. Tier 2:
  full note Markdown loads only on node click (`GET /api/vault/note?path=...`).
- **Python in-memory invalidation.** Cache parsed metadata in RAM; check
  `st_mtime` on access; selectively patch notes touched by `[WRITE_NOTE]` /
  `[APPEND_NOTE]`.
- **GPU instanced rendering & physics sleep.** `THREE.InstancedMesh` / point
  particles in one draw call; `simulation.stop()` after equilibrium (~3 s);
  animation loop halts on inactive tab.

## Consequences

**Positive**

- Sub-5 ms API responses across 20,000+ notes; < 165 MB combined RAM; 60 FPS on
  entry-level hardware; minimal battery / fan impact.

**Negative / costs**

- An in-RAM cache is per-process and must be invalidated correctly on every
  write path.

## Alternatives rejected

- **Re-walking the filesystem + regex on every request.** Rejected: 200–800 ms
  disk I/O per call.
- **Rendering one DOM element per note.** Rejected: layout thrashing, ~5 FPS at
  10,000 nodes.
