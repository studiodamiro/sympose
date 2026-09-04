---
title: "Action Tags Reference"
created: 2026-09-05
type: wiki-reference
parent: index
tags:
  - sympose/reference
  - action-tags
  - autonomic-protocol
---

# ⚡ Action Tags Reference

Agents act on the world by emitting declarative bracketed tags directly in
their response stream — `[TAG: args]`. `ActionProcessor` parses every tag
**after** the model finishes streaming its answer to you, executes the
side-effect, and strips the raw tag out of what you see, replacing it with a
confirmation badge. Nothing here costs an extra round-trip: dispatch and
generation happen in the same completion (see
[ADR-071](../../journal/2026-09/2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md)).

---

## Tags

| Tag | Purpose | Example |
| :--- | :--- | :--- |
| `[DAILY_NOTE: <content>]` | Appends a reflection to today's daily note with dynamic frontmatter tag syncing | `[DAILY_NOTE: Reflected on [[Project X]] with [[Virginia]]. #growth]` |
| `[WRITE_NOTE: <path> \| <content>]` | Creates or overwrites an Obsidian note with template frontmatter | `[WRITE_NOTE: Thoughts/creativity.md \| # Creativity\n\nNotes...]` |
| `[APPEND_NOTE: <path> \| <content>]` | Appends content to an existing vault note | `[APPEND_NOTE: Projects/roadmap.md \| - [ ] Ship v2]` |
| `[WRITE_CANVAS: <path> \| <json>]` | Creates visual Obsidian `.canvas` diagrams and mindmaps | `[WRITE_CANVAS: architecture.canvas \| {...}]` |
| `[READ_NOTE: <path>]` / `[VIEW_NOTE: <path>]` | Renders a vault note in-terminal | `[READ_NOTE: Projects/roadmap.md]` |
| `[SEARCH: <query>]` / `[WEB_SEARCH: <query>]` | Executes real-time live internet search ($0 API key) | `[SEARCH: AXS price USD]` |
| `[SPAWN_WORKER: <spec> \| <task>]` | Dispatches an ephemeral sub-agent with tools/skills | `[SPAWN_WORKER: web_search \| Research market trends]` |
| `[REMEMBER: <fact>]` | Saves a durable bullet point to working memory | `[REMEMBER: Prefers vanilla CSS over Tailwind]` |
| `[REACT: <emoji>]` | Adds an expressive emoji reaction to a Slack message | `[REACT: rocket]` |
| `[CONFIG_SET: <key> \| <val>]` | Updates and persists runtime settings in `config.yaml` | `[CONFIG_SET: performance.max_context_turns \| 20]` |
| `[CREATE_PERSONA: <handle> \| <yaml>]` | Autonomously creates a new agent. A `soul_content` field in the YAML becomes the agent's real soul directly ([ADR-075](../../journal/2026-09/2026-09-05_adr-075-persona-soul-content-in-create-persona.md)); without one, it falls back to a generic scaffold. | `[CREATE_PERSONA: archimedes \| name: Archimedes...\n soul_content: \|\n  # Archimedes...]` |
| `[DELETE_PERSONA: <handle>]` | Safely archives a retired agent profile | `[DELETE_PERSONA: archimedes]` |

---

## Malformed tags

A recognized tag whose arguments don't match its expected shape (a
`WRITE_NOTE` missing its `| content` half, an empty `READ_NOTE`, unparseable
`CREATE_PERSONA` YAML) never fails silently. `execute_actions` surfaces an
explicit `⚠️ Malformed [TAG] — ignored` badge instead, so the model — and you
— always know whether the action actually ran (ground-truth sovereignty,
[ADR-024](../../journal/2026-08/2026-08-25_adr-024-ground-truth-sovereignty-axiom.md)).

---

## Related

- **[Sandboxed Obsidian Vault](../architecture/sandboxed-vault.md)** — path validation and domain-folder rules `WRITE_NOTE`/`APPEND_NOTE`/`DAILY_NOTE` run under.
- **[Memory Architecture Standard](../memory/architecture-standard.md)** — how `REMEMBER` interacts with working memory and compaction.
- **[MCP & Sub-Agent Workers](../architecture/mcp-and-workers.md)** — what `SPAWN_WORKER` can mount and run.
