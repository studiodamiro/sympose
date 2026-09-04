---
title: "ADR-020 — The Zero-Maintenance Mandate & The Assistant Paradox"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-020 — The Zero-Maintenance Mandate & The Assistant Paradox

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Traditional agent frameworks burden the user with database administration,
vector-index maintenance, manual prompt curation, and static config upkeep. An
assistant that requires human maintenance recreates the exact cognitive load it
was built to remove — the Assistant Paradox.

## Decision

Enshrine the **Zero-Maintenance Mandate** across all components:

1. **Memory** — autonomous self-compaction and shadow extraction; no manual
   curation.
2. **Models** — live catalog discovery via `ModelCatalog`; no hardcoded
   dictionaries.
3. **Profiles** — auto-bootstrapping of souls and memories on boot; no database
   provisioning.
4. **Infrastructure** — pure file-based Markdown over the Python standard
   library; no Docker, Postgres, or ChromaDB daemons.

## Consequences

**Positive**

- The user runs Sympose, not a maintenance backlog.
- Every subsystem is judged against this mandate thereafter (cited by ADR-033,
  ADR-045, ADR-054, ADR-064, ADR-065).

**Negative / costs**

- Rules out otherwise-convenient tools (a real DB, an async dispatch layer) when
  they would add an operational surface — an accepted, deliberate constraint.

## Alternatives rejected

- **Adopting a managed datastore / vector DB / container stack.** Rejected: each
  is an operational surface the single user would have to babysit, violating the
  mandate.
