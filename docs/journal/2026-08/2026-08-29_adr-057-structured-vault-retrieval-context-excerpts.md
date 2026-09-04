---
title: "ADR-057 — Orderly Structured Vault Retrieval & Single-Line Context Excerpts"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-057 — Orderly Structured Vault Retrieval & Single-Line Context Excerpts

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`VaultManager.search()` concatenated up to 1,200 characters of raw Markdown per
matching file into one long string. With a multi-folder whitelist matching 15+
notes, the user got a chaotic wall of text.

## Decision

1. **`VaultManager.parse_frontmatter(content)`** — regex-parses the YAML head
   into a typed dict (`title`, `tags`, `author`, `created`, `aliases`), returning
   the clean body separately.
2. **`search_structured`** — traverses whitelisted folders in < 10 ms and returns
   structured dicts (`file_name`, `rel_path`, `abs_path`, `match_type`,
   `line_no`, `snippet`, `title`, `tags`, `meta`).
3. **Dedicated `#tags` line & single-line excerpts.** Header line carries the
   badge `[N]` and `(Line #)` only; frontmatter `#tags` on their own indented
   line; excerpts flattened (`" ".join(snippet.split())`) and capped at 70 chars
   with `...`.
4. **Session cache & index resolution.** `_last_searches[profile_handle]` lets
   the user reference results by number `1-N`.

## Consequences

**Positive**

- Predictable 2–3 line result cards instead of a text dump.
- Numbered results feed the T-junction note viewer
  ([ADR-058](./2026-08-29_adr-058-multisectionpanel-in-terminal-note-viewer.md)).

**Negative / costs**

- The frontmatter parser is regex-based, not a YAML library — malformed
  frontmatter degrades gracefully but not perfectly.

## Alternatives rejected

- **Raw ~1,200-character file-head dumps.** Rejected: unreadable at any real
  match count.
