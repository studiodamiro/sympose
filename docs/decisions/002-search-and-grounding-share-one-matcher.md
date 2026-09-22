# 002 — Grounding reuses search's matcher instead of a separate retrieval system

## Context

Chat needs a way to decide which vault content is relevant to a given turn before replying, so replies are grounded in real notes rather than invented — grounding is non-negotiable per this project's standing rules. Full-text search needs its own way to find matching notes for the search bar. Legacy's `vault_search.py` already had two implementations serving *search* specifically: a `direct` path (walk the parsed vault snapshot, classify each note as a title/tag/content match, return a snippet) and an opt-in `sqlite_fts` path (a SQLite FTS5 index, BM25-ranked, gated behind a persisted-settings system this backend doesn't have).

## Decision

Port only the `direct` path, as a `vault_search.py` module built on the existing `vault_snapshot.get_vault_snapshot`, and reuse it for both purposes: the search bar calls it with a user-typed query, and the chat engine calls the identical title/tag/content matcher against a user's message, automatically, to select grounding content before replying. No separate retrieval system is built for chat. `sqlite_fts` is not ported.

## Consequences

One matcher serves both search and grounding, so improving snippet quality or match classification benefits both at once — building search isn't separate work from solving grounding, it's the same work done once. Grounding has no semantic understanding: a chat message has to share actual words with the relevant note's title, tags, or body, not just meaning, for that note to surface. A vault user who phrases things very differently from how their notes are written may get weaker grounding than a semantic retriever would provide.

## Alternatives rejected

- **`sqlite_fts`** (BM25-ranked SQLite index) — real scale infrastructure, but it doesn't pay for itself at personal-vault scale, and it depends on a persisted-settings system (`config_manager`) this backend doesn't have. Revisit if vault size or query volume ever makes the plain walk genuinely slow.
- **Embeddings / vector search** — would catch meaning-based matches `direct` misses, but is a materially bigger, different piece of infrastructure (an embedding model, a vector store, re-embedding on every vault edit) for a frugality-first product, before the simpler mechanism has even been shown insufficient. Not ruled out permanently, just not justified ahead of trying the simpler approach first.
