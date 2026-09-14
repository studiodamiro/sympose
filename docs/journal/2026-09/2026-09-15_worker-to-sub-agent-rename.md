---
entry: 2026-09-15
created: 2026-09-15 00:00
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - naming
---

# Sympose Engineering Log: Worker → Sub-Agent Rename

> **Date:** Tuesday, September 15, 2026
> **Topic:** Closing the deferred half of the Agent → Persona naming split
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Backend, config, CLI, and wiki done. UI (`ui/src`) and the
> compiled `webui` bundle are the one piece still open.

---

## 1. How this surfaced

The day before, working through the Sympose Audit's dependency-ordered plan,
the team split "agent" into three distinct words: **persona** (who you're
talking to — Samantha, Grace, Aurelius), **agent** (freed up for a real
future autonomous, goal-directed capability, not yet built), and
**sub-agent** (reserved for the existing `[SPAWN_WORKER]` mechanism). The
Agent → Persona half of that rename was executed end-to-end that day —
tagline, CLI, API, dashboard, wiki, every model-facing prompt/skill/soul
file. The Worker → Sub-Agent half was deliberately scoped out as separate
work, flagged repeatedly in that session as "separate, not started."

Picked back up today after closing every item on the audit's own punch
list — vault.py's split, the models.py provider-key consolidation, the
already-fixed SPAWN_WORKER delimiter-fragility check, the nebula wiki gap,
and the Slack session-history question resolving itself once DM continuity
was fixed. With nothing else left on that list except the (deliberately
last) web dashboard chat wiring, damiro asked to close this one next: "yes,
hard rename. let the problems run down now" — no backward-compatibility
aliasing for the persisted config keys or the env var.

## 2. Scope, traced before writing any code

Per damiro's own standing preference (list dependencies before starting so
nothing gets discovered mid-implementation), the full surface was grepped
and categorized before any edit:

- **Purely mechanical, no decision needed**: `sympose/workers.py` →
  `sub_agents.py`, `WorkerEngine` → `SubAgentEngine`, `WorkerTask` →
  `SubAgentTask`, `execute_worker_task/stream` →
  `execute_sub_agent_task/stream`, `_build_worker_context` →
  `_build_sub_agent_context`, the `"worker"` sentinel handle string in
  `actions.py`, `tests/unit/test_workers.py`, 13 wiki pages plus one whose
  filename was literally the old name
  (`docs/wiki/architecture/mcp-and-workers.md`).
- **Real decisions, damiro's call**: the model-facing tag
  `[SPAWN_WORKER: ...]` (yes, rename it too, for full internal
  consistency — nothing about the tag is visible to a human, but the
  model and the parser both need to agree on it); the `/worker` CLI
  command (renamed to `/subagent`, matching the already-existing
  `subagent_spawn` skill name rather than inventing a new pattern); three
  persisted config keys (`performance.max_worker_tool_turns`,
  `worker.shell_allowlist`, `worker.shell_command_timeout`) and one env
  var (`DEFAULT_WORKER_MODEL`) — all hard-renamed, no aliasing.
- **Deliberately out of scope**: `performance.hygiene_workers` and any
  "worker thread pool" language (an unrelated, generic concept — the
  background hygiene thread pool, not this mechanism), the model-flavor
  text "agentic worker" describing a third-party model's own general
  nature, two same-named-by-coincidence `_worker()` closures in
  `memory.py`/`sessions.py` (background summarization helpers, unrelated),
  and every historical ADR/journal entry — frozen record, same convention
  already established for the Agent → Persona rename the day before.

## 3. A real gap the test suite caught, not a manual review

The backend rename (Python identifiers, the tag, persisted config, the CLI
command) was committed first, verified against the full test suite — 574
tests, all passing, 10 of them needing their own updates that the suite
itself surfaced rather than anything found by inspection.

Moving on to the wiki docs turned up a real miss: **the model-facing prompt
files that actually teach a persona the tag format** —
`sympose/prompts/workspace_rules.md` and the `subagent_spawn` /
`vault_recall` / `web_search` `SKILL.md` playbooks — still taught the old
`[SPAWN_WORKER: ...]` spelling. The parser now only recognizes
`SPAWN_SUB_AGENT`. Any persona following those instructions as written would
have emitted a tag the runtime no longer matches at all — not even the
malformed-tag fallback catches an unrecognized tag *name* — so a delegation
attempt would have silently printed as inert literal text in the reply
instead of running. Caught by re-grepping `sympose/` for `SPAWN_WORKER`
while working through the docs, not by the test suite (none of the existing
tests exercise the packaged prompt files' actual content against the live
parser) — fixed in its own commit immediately, ahead of the wiki work.

## 4. What's still open

The two `ui/src` files with "worker" in them
(`components/sympose/action-badge.tsx`, `routes/components-gallery.tsx`)
and the compiled `sympose/webui/` bundle, which still contains the string
`SPAWN_WORKER` from before this rename and needs a rebuild once `ui/src` is
updated. Everything else — every Python identifier, the wire-format tag,
persisted config, the CLI command and its tab-completion, and all wiki/
journal-index prose that isn't a frozen historical record — is done.

## 5. Commits

- `a887c1c` — backend: Python identifiers, the tag, persisted config, the
  CLI command, test suite updates.
- `d9011ae` — fix: the model-facing prompt/skill files missed in the
  backend pass (§3 above).
- `01bc5b7` — docs: all wiki pages, the `mcp-and-workers.md` →
  `mcp-and-sub-agents.md` rename and full content rewrite, `.agents/rules/`
  sync.
