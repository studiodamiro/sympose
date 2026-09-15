---
title: "Vault Agent Capability Reference & Roadmap"
created: 2026-09-16
type: wiki-reference
parent: index
tags:
  - sympose/reference
  - vault_read
  - sub-agents
  - roadmap
---

# Vault Agent Capability Reference & Roadmap

What a `vault_read`-skilled sub-agent can already do deterministically, what
Sympose already has the data for but hasn't wired up yet, and what's a
genuinely open problem. Users increasingly expect an AI-integrated vault to
answer things a human wouldn't bother computing by hand — this page tracks
that gap so it doesn't just live in a conversation.

## Built and live

Tools available to any sub-agent with the `vault_read` skill
(`sympose/sub_agents.py`, `_VAULT_TOOL_SCHEMAS`):

- **`vault_search(query, folder=None, max_results=10)`** — ranked full-text
  search with snippets, over the SQLite FTS5 index (ADR-070.5), optionally
  folder-scoped. One structured call instead of `grep`.
- **`vault_sample(folder, count=1)`** — real, full content of one or more
  randomly sampled notes from a folder, in a single call. Purpose-built for
  "pick a random note" / "surprise me" requests.

Both wrap existing, already-sandboxed `VaultManager` primitives rather than
adding new retrieval logic — see journal
[2026-09-15_samantha-live-testing-bug-sweep.md §3.38](../../journal/2026-09/2026-09-15_samantha-live-testing-bug-sweep.md).

## Data already exists, not yet exposed to an agent

- **Wikilink / backlink counting and connection queries** — "how many notes
  link to `[[AI]]`", "what references this note". `vault_links.py` already
  has a cached, mtime-invalidated inverted backlink index
  (`build_backlink_index`) and `VaultManager.get_backlinks_digest(profile,
  note_name)` returns an exact count plus every referencing note with
  context. `resolve_turn_context` already answers this deterministically
  (zero round-trips) for specific phrasings ("what notes link to X", "who
  references X", "backlinks for/to X") — but a naturally-phrased question
  outside that pattern falls through to a sub-agent that has no equivalent
  tool, and would reconstruct it via `grep -r "\[\[AI"`, missing aliased
  links (`[[AI|Artificial Intelligence]]`) and heading-anchored links
  (`[[AI#section]]`).
  - **Next step:** add `vault_backlinks(target)` to `_VAULT_TOOL_SCHEMAS`,
    wrapping `get_backlinks_digest` the same way `vault_search`/
    `vault_sample` wrap their primitives. Small — same shape as the work
    already done.
- **Multi-keyword wikilink connection queries** — "pull the notes connected
  via wikilinks for these keywords" (plural). No single function does
  "backlinks for several targets, combined" today, but nothing new needs
  building for it either: once `vault_backlinks` exists, a sub-agent making
  one call per keyword and combining results covers this.

## Genuinely unsolved

- **Aggregate/counting questions** — "how many daily entries did I write in
  2023". Confirmed live (`ollama/gemma4:e4b`, 2026-09-16): the sub-agent
  called `vault_search(query="2023", folder="Daily")`, which caps at ~10
  ranked results and cannot count a full corpus. Worse, a **known defect**
  compounds this: the 3.37 fabrication safety net
  (`SubAgentEngine._content_unread`) assumes a synthesis citing a note it
  didn't fully read is always the "invented content" case, and swaps in
  that one note's raw content — producing a nonsensical answer to a
  counting question (a single unrelated note dump, not a number) instead of
  either a real count or an honest "I can't count that precisely." The
  safety net needs a way to recognize an aggregate/counting question shape
  and not apply the single-note swap-in to it.
- **Bulk / full-corpus synthesis** — "summarize my whole being for 2019
  using my daily notes." No tool reads every note across a date range or
  topic and synthesizes across it; `vault_search`'s ~10-result cap and the
  sub-agent's tool-turn budget (default 8) both fall far short of what a
  full year of daily notes would require. Confirmed live: the model
  under-searched, falsely reported "I have no record of that" for a year
  that does have an entry, and leaked raw tool-call JSON into its final
  text instead of prose. This needs a fundamentally different mechanism —
  something like a chunked or map-reduce pass over N notes — not an
  extension of the current single-call tools.

## Shapes the wider Obsidian ecosystem has already converged on

No academic taxonomy of "things people do with a personal knowledge vault"
exists, but a crowdsourced one effectively does: the Obsidian community
plugin directory (7,600+ plugins) and, more usefully, **Dataview** — the
ecosystem's de facto standard for treating a vault as queryable data. Every
note becomes a record (frontmatter fields, inline fields, tasks, links),
and Dataview settles on four query shapes as the complete surface: **LIST**,
**TABLE**, **TASK**, **CALENDAR** (basic queries read as plain English;
DataviewJS covers anything more custom). Mapped against where this page
already stands:

| Dataview shape | What it means | Sympose coverage |
|---|---|---|
| LIST / TABLE | Filtered/sorted lookups, ranked results | `vault_search` (built) covers full-text lookups; a *structured field query* (filter by frontmatter, e.g. `tags: project AND status: active`) is still a gap — `vault_search` only matches text/snippets, not typed frontmatter fields |
| TASK | Query checkbox items (`- [ ]` / `- [x]`) across notes | Nothing today — no tool reads or filters to-do items specifically |
| CALENDAR | Date-range / chronological queries | Partial — `vault_sample` random-picks within a folder, daily-note logic exists, but there's no general "everything between date X and Y" tool. This is also exactly what the "aggregate/counting" and "full-corpus synthesis" gaps above need underneath them |

Useful less as a spec to copy and more as external validation that the four
gaps already listed on this page (structured field filtering, task
querying, date-range querying, and the synthesis layer built on top of it)
aren't a guess at what users will want — they're the same shape a mature,
independent ecosystem already converged on for this exact kind of data.

## Design note for whoever picks these up

Round-trip frugality still applies: prefer extending the deterministic
`resolve_turn_context` fast path (zero LLM calls) for any phrasing that can
be recognized structurally, and reserve sub-agent tool calls for what
genuinely needs a model in the loop. The backlink and multi-keyword items
above fit that pattern cleanly; full-corpus synthesis inherently does not
(it needs the model to actually read and reason over the content) and
should be scoped as its own piece of work rather than bolted onto the
existing single-call tools.
