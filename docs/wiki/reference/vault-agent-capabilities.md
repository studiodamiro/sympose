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

## Prioritized punch list

Ordered by cost-to-build, each cross-referenced to the UI surface it would
power — `ui-design-reference.md` §6.5 (Vault Explorer) already speced
several of these panels ahead of having real data behind them:

| # | Tool | Cost | Wraps | UI surface it powers |
|---|---|---|---|---|
| 1 | `vault_by_date(start, end, folder=None)` | Cheap | `find_chronological_notes` (already exists) | §6.5's **Daily Reflections calendar view** — currently speced with no data source; this is it. Also fixes the counting-question defect above (a real count instead of the swap-in-hijack) |
| 2 | `vault_by_tag(tag, folder=None)` | Cheap | Manifest's already-indexed `tags` per node | §6.5's **YAML frontmatter inspector + tag editor** |
| 3 | `vault_backlinks(target)` | Cheap | `get_backlinks_digest` (already exists, exact) | §6.5's **Backlink & Mention inspector side panel** — explicitly speced as "powered by the inverted index," which already exists; this tool is what makes it queryable from chat too, not just the dashboard's own direct API call |
| 4 | `vault_tasks(status=None, folder=None)` | Medium — no checkbox index exists yet | New: needs either a manifest extension or a live per-note scan | Not yet speced in the UI doc — building this tool and a UI panel for it should happen together |

Deliberately still not planned: arbitrary frontmatter-field filtering
beyond tags (needs a manifest schema change, no concrete need yet),
full-corpus synthesis (a genuinely different mechanism — chunked/map-reduce
over N notes), and adopting an external Obsidian MCP server (real prior art
exists — e.g. `joch/obsidian-connect-mcp` for Dataview-style queries,
`aaronsb/obsidian-mcp-plugin` for graph/task/hybrid search — but plugging
one in means vetting whether it respects Sympose's per-persona `allowed_dirs`
sandbox, plus its own ADR per the project's dependency policy; not a quick
add). Also worth knowing: Dataview itself has been reportedly dormant since
April 2025, with Obsidian's native **Bases** feature (1.9+) as the
implicit successor — a reason to keep #1-4 above general rather than
building tightly around Dataview's specific query syntax.

## The real bottleneck is local-model reliability, not tool availability

Every tool above only helps if the model calling it behaves. Live evidence
from this same session, all with the *same* task and the *same* tools
available, varied wildly run to run on `ollama/gemma4:e4b`:

- Redundant tool calls for identical intent (two `find` variants back to
  back; `vault_sample` called twice in a row for one random pick).
- Unrelated tangents mid-task — one run answered "how many entries in
  2023" by identifying itself as "Gemma 4, developed by Google DeepMind"
  instead of continuing the task.
- Raw tool-call JSON leaking into the final answer instead of prose, on
  a run that otherwise had the real content sitting right there in its own
  tool-call history.
- The same "pick a random note" task getting a clean, correct answer on
  two runs and a broken one on a third — no code changed between them.

None of this is fixed by adding more tools; it's model behavior under the
same tool surface. Two implications for anything built from the punch list
above: (1) keep leaning on `resolve_turn_context`'s deterministic fast path
(zero LLM calls) for any phrasing recognizable structurally — it's the only
way to fully sidestep this, since a sub-agent tool call is always at the
mercy of whichever model is driving it that turn; (2) any new tool needs
its own fabrication/sanity check in the same spirit as 3.37's
`_content_unread` and the counting-question defect noted above — assume
the model calling it will occasionally go off-script, because on a small
local model it reliably does.

**Reproduced again, 2026-09-17**, same model, a new specific trigger: asked to
summarize a real note in its own words, `gemma4:e4b` called a tool name
(`assistant()`) that was never offered to it in the schema, then on one run
recovered by continuing (later corrected via `_content_unsupported` +
`_content_unread` — see the
[2026-09-17 journal entry](../../journal/2026-09/2026-09-17_sub-agent-unsupported-synthesis-guard.md))
and on another derailed entirely into self-identification
(`{"name": "Gemma 4", "developer": "Google DeepMind", ...}`) instead of
answering at all — the same "unrelated tangent" shape from the bullet list
above, just with a hallucinated-tool-call trigger this time. Confirms
implication (2) still holds even with two more structural checks live: a
grounding check can only catch an *unsupported claim*, and this case makes
no claim to check — it just gives up on the task. The actual fix for this
shape is narrowing the tool surface per model tier (fewer live choices per
turn = less room to invent one that isn't there), which is exactly what
ADR-122 (Local/Cloud Model Routing by Message Complexity — accepted, still
implementation-pending) already proposes. Not yet built.
