---
title: "ADR-133 — wiki_ingest Skill"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-133 — wiki_ingest Skill

- **Status:** Implemented and verified against a real model.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

ADR-132 shipped the LLM Wiki layer's scaffolding with no ingest behavior
yet. This ADR is the "ingest" operation of Karpathy's three (ingest,
query, lint): given a raw source, file it into wiki pages. Deliberately
prompt-only — no new tags, no new execution code in `actions.py` — since
the existing `[WRITE_NOTE]`/`[APPEND_NOTE]` tags already do everything
this needs; the actual content is a playbook, not a mechanism.

## Decision

- **`skills/wiki_ingest/SKILL.md`**: `minimum_capability_tier: standard`
  (ADR-127/128's first real consumer beyond the dormant-primitive stage),
  a `recommended_models` list, and a playbook that: reads the source
  without modifying it, writes/updates one wiki page per real topic (not
  one page per source), links related pages with `[[Wikilink]]`, and —
  the one genuinely load-bearing instruction — writes its own frontmatter
  block directly in the `[WRITE_NOTE]` payload, `summary:` included,
  rather than relying on any template. Ends by appending a timestamped
  event to `log.md` via `[APPEND_NOTE]`.
- Shipped in `sympose/builtin_skills/wiki_ingest/` — the single source
  of truth `SkillManager` scans and `pyproject.toml` packages (confirmed
  by re-reading ADR-020's consolidation history: the repo-root `skills/`
  directory is gitignored, runtime-seeded scratch output, never a real
  source location — an earlier draft of this ADR wrongly cited a
  "`vault_recall` is workspace-only" precedent that turned out not to
  exist; `vault_recall` was simply renamed to `vault_read` and has always
  lived in `builtin_skills/`). Living in `builtin_skills/` does not make
  a skill active for any persona by default — that still requires a
  persona's manifest to list it by name in its `skills:` array, which
  Samantha's does not. This stays an opt-in Tier-3 feature
  (`wiki.root` defaults to disabled) regardless of packaging location.

## Consequences

**Positive — verified with a real model, not just read back for
plausibility.** Set up a scratch workspace (`wiki.root: Wiki`, a test
persona scoped to `vault_folders: ["Wiki/"]` with only the `wiki_ingest`
skill active) and ran a real turn through `PersonaEngine.chat_stream`
against Gemini. The actual output:

```yaml
---
title: Ollama Keep-Alive
tags: [wiki]
summary: Explains the keep_alive parameter in Ollama for managing model idle timeouts and memory retention.
---

Ollama unloads models from memory after an idle timeout controlled by the `keep_alive` parameter.

- Setting `keep_alive` to `-1` keeps the model resident in memory indefinitely.
- Setting `keep_alive` to `0` unloads the model immediately after completing a request.
```

and `log.md` gained: `2026-09-19 — ingested "Ollama Keep-Alive" → wrote
[[Ollama Keep-Alive]]`. The model wrote genuine, non-templated frontmatter
(a real `summary:` line compressing what the page actually says, not a
placeholder), stayed inside its sandbox, and logged the event in
approximately the instructed shape — confirming the "write your own
frontmatter" instruction actually lands with a real model, not just in
theory.

**Negative / costs**
- The log entry the model produced (`2026-09-19 — ...`) omitted the
  time-of-day the skill's own example showed (`2026-09-19 14:02 — ...`) —
  a minor format drift, not a functional problem (the log is
  human/AI-readable prose, not a parsed format), but worth knowing a real
  model won't necessarily match an example's format exactly.

## Alternatives rejected

- **A new `[INGEST_SOURCE]` tag with bespoke execution logic in
  `actions.py`.** Rejected — the existing tag vocabulary already covers
  everything ingest needs to do (write a page, append a log line); a new
  tag would duplicate `write_note`/`append_note` mechanics that already
  exist.
- **Leaving `wiki_ingest` in the gitignored, runtime-seeded repo-root
  `skills/` directory instead of `sympose/builtin_skills/`.** This is
  what actually shipped first, on a mistaken belief that it matched a
  "`vault_recall` is workspace-only" precedent. Re-checked against git
  history while preparing to commit this ADR: no such precedent exists —
  `vault_recall` was renamed to `vault_read` and has always lived in
  `builtin_skills/`; the repo-root `skills/` directory is disposable
  scratch output `_seed_builtin_skills` regenerates from `builtin_skills/`
  on every run, never tracked by git. A skill living only there would
  never actually ship — not to PyPI, not even to another checkout of this
  repo. Corrected before commit by moving it to `builtin_skills/wiki_ingest/`.
  Being discoverable there doesn't make it active by default: that still
  requires a persona's manifest to list `wiki_ingest` explicitly, which
  no shipped persona does.
