---
title: "LLM Wiki Layer (Tier 3, Opt-In)"
created: 2026-09-19
type: wiki-architecture
parent: architecture/overview
tags:
  - sympose/wiki
  - obsidian-vault
  - adr
---

# 🧠 LLM Wiki Layer (Tier 3, Opt-In)

Sympose's default mode treats your vault as human-authored ground truth:
personas read it, and may be invited to append to it via `[WRITE_NOTE]`/
`[APPEND_NOTE]`, but never autonomously rewrite or reorganize what you've
written. The LLM Wiki layer is a deliberate, opt-in exception to that
boundary, scoped to a folder the AI is explicitly given ownership of —
following Andrej Karpathy's pattern for AI-maintained knowledge bases
(ADR-132/133/134).

Disabled by default (`wiki.root` is empty). Nothing described here has
any effect until you set it.

## The three layers

| Layer | What it is | Who edits it |
| --- | --- | --- |
| **Raw sources** (`wiki.root/wiki.raw_sources_subdir`, default `Sources/`) | Curated originals — articles, transcripts, notes you drop in | You. AI reads, never edits. |
| **Wiki pages** (everything else under `wiki.root`) | AI-generated markdown — summaries, entity pages, concept pages, comparisons | The `wiki_ingest`/`wiki_lint` skills. |
| **Schema** (`wiki.root/wiki.schema_file`, default `WIKI.md`) | Explains the convention, seeded automatically | Seeded once; safe to hand-edit afterward. |

A chronological, append-only `wiki.root/wiki.log_file` (default `log.md`)
records every ingest and lint event.

## The three operations

- **Ingest** (`wiki_ingest` skill) — hand a source to a persona with this
  skill active; it files it into wiki pages, writes its own frontmatter
  (including a one-line `summary:` — no template can generate that
  content, so the skill writes it directly rather than relying on
  auto-fill), and logs the event.
- **Query** — no dedicated skill. Once content lives under an ordinary
  vault path, `vault_recall` already serves it.
- **Lint** (`wiki_lint` skill) — health-checks the wiki for
  contradictions, stale claims, and orphan pages (no inbound links,
  detected via the existing vault manifest graph — no parallel index).
  Report-only by default; a persona-scoped `lint_auto_fix` setting
  (**your discretion, per persona** — off unless you explicitly trust
  that persona to self-correct) allows it to also edit flagged pages
  directly, still confined to `wiki.root` either way.

## How the sandbox guarantee actually holds

There's no special-cased "wiki mode" enforcement anywhere in the code.
The convention is: give a dedicated persona (e.g. `wiki-curator`)
`vault_folders: ["Wiki/"]` (or whatever you set `wiki.root` to) — the same
`is_safe_path`/`get_allowed_dirs` sandboxing every persona already has
makes every tool that persona gets physically incapable of reaching
anything outside that path. This is also why `wiki_bootstrap.py` seeds
nothing outside `wiki.root` itself (no auto-seeded note template in your
vault's `Templates/` folder, for instance) — a narrowly wiki-scoped
persona couldn't reach it anyway, and it isn't needed once `wiki_ingest`
writes explicit frontmatter.

## Configuration

See the [Configuration Reference](../reference/configuration.md)'s "LLM
Wiki (Tier 3, opt-in)" section for `wiki.root`, `wiki.raw_sources_subdir`,
`wiki.schema_file`, `wiki.log_file`, and the persona-scoped `lint_auto_fix`.

## Full history

[ADR-132](../../journal/2026-09/2026-09-19_adr-132-llm-wiki-layer-scaffolding.md) ·
[ADR-133](../../journal/2026-09/2026-09-19_adr-133-wiki-ingest-skill.md) ·
[ADR-134](../../journal/2026-09/2026-09-19_adr-134-wiki-lint-skill-user-controlled-auto-fix.md)
