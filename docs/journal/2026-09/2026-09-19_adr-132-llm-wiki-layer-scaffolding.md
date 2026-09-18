---
title: "ADR-132 — LLM Wiki Layer: Raw/Wiki/Schema Convention & Config Knobs"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-132 — LLM Wiki Layer: Raw/Wiki/Schema Convention & Config Knobs

- **Status:** Implemented. Scaffolding only — ingest and lint behavior are
  ADR-133/134.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Tier 3 of the comparison against Tina Huang's Obsidian video is Andrej
Karpathy's LLM Wiki pattern: an AI-maintained knowledge base with three
layers (immutable raw sources, an AI-owned wiki, a navigation schema) and
three operations (ingest, query, lint). Earlier scoping already ruled out
one piece of the original plan: a separately persisted `index.md`
duplicating what `vault_manifest.py`/`vault_links.py` already compute and
serve today (the Knowledge Nebula, `vault_recall`'s Vault Structure Map).
This ADR ships everything else — the folder convention and its config
knobs — with zero ingest/lint behavior yet, so the sandbox guarantee
(explained below) is established before anything writes AI-generated
content into it.

## Decision

- **`sympose/config_settings_wiki.py`**: a new `LLM Wiki (Tier 3, opt-in)`
  section — `wiki.root` (str, default `""`, the off-switch), `wiki.
  raw_sources_subdir` (default `"Sources"`), `wiki.schema_file` (default
  `"WIKI.md"`), `wiki.log_file` (default `"log.md"`). No separate
  `index.md` setting, per the earlier finding.
- **`sympose/wiki_bootstrap.py`** (80 lines): `bootstrap_wiki_layer(profile)`
  — no-op unless `wiki.root` is set, then seeds the schema file and
  `log.md` via `vault_write.create_note` (refuses rather than overwrites,
  so a user's own edits survive later reloads) and the raw-sources
  subfolder via `create_folder`. Hooked into `ProfileManager.
  bootstrap_missing_artifacts`, the same "seed missing artifacts on every
  reload" pass soul/memory files already use — but writing into the
  *vault* via the existing sandboxed write path, not the workspace
  `profiles/` directory, so a persona whose sandbox doesn't reach
  `wiki.root` harmlessly no-ops (`NOTE_DENIED`) rather than erroring.
- **The sandbox is the enforcement mechanism, not new code.** The
  convention: a dedicated persona (e.g. `wiki-curator`) gets `vault_folders:
  ["Wiki/"]` (or whatever `wiki.root` is) — the existing `is_safe_path`/
  `get_allowed_dirs` check already makes every tool that persona has
  physically incapable of reaching anything outside that path. This is
  what will guarantee ADR-134's lint pass can never touch a user's real
  authored notes, established here before lint exists to need it.
- **Query needs no new code** — once wiki content lives under an ordinary
  vault path, `vault_recall` already serves it.
- **No auto-seeded "Wiki" note template.** The original plan called for
  one (a `summary:` frontmatter field via the ADR-040 Templates engine),
  but seeding it would require write access to the vault's `Templates/`
  folder — outside `wiki.root` by design, so a narrowly wiki-scoped
  persona (the intended, sandboxed common case) could never create it.
  Templates also can't express model-generated content anyway (no
  placeholder exists for it) — ADR-133's `wiki_ingest` skill instead
  instructs the model to write its own frontmatter block directly,
  `summary:` included, which is real content a template could never
  produce.
- 7 new unit tests (`tests/unit/test_wiki_bootstrap.py`): no-op when
  unset, seeds all three artifacts when set, respects custom subdir/
  filenames, doesn't clobber a hand-edited schema file, idempotent across
  repeated calls, silently no-ops for an out-of-scope persona, normalizes
  a root path with stray slashes.
- **Verified against a real vault, not just mocks**: ran
  `bootstrap_wiki_layer` and a real ingest turn (ADR-133) together against
  a scratch workspace with a real Gemini call — see ADR-133's Consequences
  for the actual output.

## Consequences

**Positive**
- Entirely inert by default (`wiki.root` unset) — zero cost, zero new
  behavior, for every existing installation.
- The Templates-seeding removal is a real simplification, not a
  compromise: the thing it would have provided (a `summary:` scaffold)
  turned out to need model-generated content a template mechanically
  cannot supply, so ADR-133 was always going to need explicit
  frontmatter instructions regardless.

**Negative / costs**
- No template scaffold means a page written by hand (not through
  `wiki_ingest`) gets no automatic `tags`/`summary` starter — acceptable,
  since the wiki layer's whole premise is AI-authored pages, not manual
  ones.

## Alternatives rejected

- **A separately persisted `index.md`.** Rejected in an earlier scoping
  pass — `vault_manifest.py` already persists the vault's structural
  index; a second file would duplicate it and drift independently.
- **Seeding the Templates/ scaffold anyway, tolerating `NOTE_DENIED` for
  a narrowly-scoped persona.** Rejected — this would make the feature's
  actual behavior depend on which persona happens to bootstrap first
  (Samantha with full access seeds it, a dedicated wiki-curator doesn't),
  an unpredictable, hard-to-explain outcome for something with no real
  payoff once `wiki_ingest` was going to write explicit frontmatter
  anyway.
- **Requiring `wiki.root` to already exist as a folder before enabling
  the feature.** Rejected — `create_note`/`create_folder` already create
  intermediate directories as needed; requiring a manual pre-step would
  just be friction with no safety benefit.
