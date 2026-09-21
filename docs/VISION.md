# Sympose — Vision

## What Sympose is

A cheap, low-round-trip AI companion for direct dialogue with an Obsidian
vault: a persona (Samantha, by default) talks to the user in tandem with
their vault instead of through expensive multi-call orchestration.

## Current state

- **Dashboard — done.** Vault browsing, the editor, note/folder CRUD,
  trash recovery, the Knowledge Nebula graph.
- **Everything else in this document — not built yet.** No LLM call
  exists anywhere in the codebase. This document describes what the rest
  of the product should become, and in what order.

## Product principles

- **Round-trip frugality is a tunable dial, not an absolute mandate.**
  Keeping LLM round-trips cheap is the founding motivation for Sympose's
  design, but it flexes for users who want reliability over minimum
  cost. Weigh added round-trips explicitly; don't assume the cheapest
  option is always correct.
- **Vault grounding is zero-hallucination, non-negotiable.** Every claim
  a persona makes about the vault must be backed by real vault content.
  Any regression here is a bug to fully restore, not a tradeoff to weigh.
- **Samantha is the only persona that ships as a product default.** Other
  personas are the user's own local customizations or illustrative
  examples, never committed as if they were shipped defaults.
- **Local-first models, cloud opt-in.** See "Lesson from legacy" below —
  this has to be the literal default a fresh install runs with, not just
  a supported option nobody reaches for.
- **A tool that has to be constantly fixed is working against the person
  it's meant to help.** Sympose should be able to configure and maintain
  itself through conversation with Samantha — creating new personas,
  tuning the installation — rather than forcing the user into a separate
  settings surface they have to fight with.

## Lesson from legacy

Legacy (`sympose-legacy`) had real local-model plumbing —
`model_router.py` warmed and kept Ollama models alive, detected local
vs. cloud backends — but its actual default was
`DEFAULT_CHAT_MODEL = "gemini/gemini-3.6-flash"`, a cloud model. The
infrastructure for "cheap and local" existed but wasn't what a fresh
install actually did. That gap between the pitch and the default is
treated as the likely cause of legacy's cost/reliability problems, and
the fix is structural: local has to be the default, cloud the opt-in,
not the reverse.

## Scope

### Full-text search (next up, UI first)

The existing search bar (`app-shell.tsx`'s `vaultSearch` field) currently
only filters the already-loaded tree by filename, tags, and links — it
never touches note bodies, matching `CLAUDE.md`'s "no full-text search"
note accurately.

Legacy's `vault_search.py` has two implementations: a `direct` path
(walks the parsed vault snapshot, classifies each note as a title/tag/
content match, returns a snippet) and an opt-in `sqlite_fts` path (a
SQLite FTS5 index, BM25-ranked, gated behind a config system this repo
doesn't have). Only `direct` is worth porting — it already reuses
`get_vault_snapshot`, which this backend already has, mtime-cached.
`sqlite_fts` is real scale infrastructure that doesn't pay for itself at
personal-vault scale.

Plan: a `vault_search.py` module ported from the `direct` path's
classification logic, trimmed of CLI-only concerns (`format_search_digest`
Markdown formatting, `get_last_search`/`/read <n>` terminal session
state). New route `GET /api/vault/search?q=...` returning
`{query, results}` — the shape the old dashboard's own `_search_vault`
docstring already sketched. Frontend: wire the existing search bar to
this route instead of (or alongside) the local tree filter.

This search implementation is also the grounding mechanism for chat (see
below) — building it once serves both.

### Multi-vault

One active vault at a time, switchable — not multiple vaults open or
searched simultaneously, which would require adding a vault dimension to
every sandboxing/persona check in the backend. `MASTER_VAULT_PATH`
becomes a list of configured vault paths; the backend tracks which one
is active (`GET /api/vaults`, `POST /api/vaults/active`). The UI trigger
is a Slack-style workspace-switcher popover hung off the existing brand
mark (`<Logo>` + "Sympose" wordmark, present in both `top-bar.tsx`'s
phone header and `main-menu.tsx`'s desktop rail) — no new chrome needed.

### Chat core: one engine, many channels

Legacy already proves the right shape: there's no `/api/chat` route in
its `server.py` — the CLI and Slack both call one shared `PersonaEngine`
directly as a library. Keep that pattern. Build the engine once (turn
handling, grounding, memory, model routing); each channel — the
dashboard chat panel, Slack, the CLI, future Telegram/WeChat — is a thin
adapter translating that channel's inbound events into an engine turn
and the engine's reply back into that channel's native format.

**Channels, in order:** Slack first — the user already lives there, and
it's the way to reach the vault remotely, away from the desktop dashboard.
Telegram/WeChat are future channels using the same adapter pattern, exact
choice undecided. The dashboard gets a chat panel too, for testing the
engine without needing external channel credentials wired up.

**CLI — chat without the dashboard.** The CLI is architecturally the
simplest channel of all: no HTTP layer, no network protocol, terminal
input calls the engine directly and prints the reply, same as Slack
calls it. But it's a different *scope* of channel than Slack or the
dashboard panel, worth splitting explicitly rather than bundling into
the core engine milestone:

- A **minimal CLI** (read a line, send it to the engine, print the
  reply, a couple of session commands) ships alongside the engine
  itself — small, and it's what makes "chat works without the dashboard
  running" true from day one.
- The **full CLI UI/UX** legacy had — `rich`-based streaming render, a
  "thinking" spinner, slash-command dispatch (`/read`, `/switch`,
  `/save`, ...), tab completion (`cli.py` + `ui.py` + `commands.py` +
  `completer.py`, ~2,500 lines combined) — is its own separate scope,
  comparable in size to the dashboard frontend itself, since a terminal
  has to build its own UX from scratch rather than getting it free from
  Slack's client or React. Not a prerequisite for the minimal CLI; a
  later milestone layered on top of it.
- **Persistent input belongs in that later milestone, not the minimal
  CLI.** The goal (matching how this very Claude Code session behaves)
  is an input line that stays live and typeable while a reply is still
  streaming above it — never blocking, same spirit as message queueing
  elsewhere. Legacy's CLI can't do this: `cli.py` uses `rich.prompt.Prompt`,
  a blocking call that halts the whole thread until Enter is pressed, one
  turn at a time. A genuinely persistent input needs a different
  foundation — `prompt_toolkit`'s full-screen mode or `textual` (a split
  always-live input region plus a separately streaming output region) —
  not a small swap over `rich`. The minimal CLI ships as a plain blocking
  loop first; persistent input is full-CLI-UX polish layered on later.

**Slack connection & authorization.** Socket Mode (as legacy used), not
incoming webhooks — Sympose opens an outbound connection *to* Slack, so
there's no public URL, no signing-secret verification, nothing to expose
to the internet. Dependencies: the `slack-bolt` library, plus a Bot
Token and an App-Level Token from a Slack App created once in the
workspace. Legacy filters *which events* it reacts to (DMs, or thread
replies) but never checks *who* sent them — anyone who can DM the bot in
the workspace reaches whatever the resolved persona can read. The fix is
a single owner-only allowlist check (one Slack user ID, rejected early,
before anything reaches the engine) on top of the existing DM/thread
filter — matches the standing "single-user, not multi-tenant" non-goal,
not a placeholder for broader access control later.

**Chat UI**: legacy already has a working, static mockup —
`chat-panel.tsx` (transcript + composer dock), `chat-message.tsx`
(message bubbles), `action-badge.tsx` (inline action-event chips),
`persona-pill.tsx`, `meta-text.tsx`, plus two layout hooks
(`use-fill-width.ts`, `use-transient-flag.ts`) that make the chat panel's
width track its neighbors live as panels open/close. Presentational only
— no send handler, no backend wiring — ready to port as-is and sit inert
until the engine exists behind it. Restores the desktop 3-panel cap
(`content`, `editor`, `chat`) that was reduced to 2 when chat was
stripped during the rewrite.

**Composing directly in the editor.** When a chat instruction is about
writing ("compose me a letter," "make this louder," "delete this one"),
the note being written is the actual reply — so instead of only showing
the new text in a chat bubble, the editor pane animates the transition:
diff the old content against the new, visually "type" the inserted parts
and "delete" the removed parts, rather than an instant content swap.
Same visual idea as the streaming caret already in the chat mockup,
applied to the editor instead of a chat bubble. This stays turn-based,
not real-time multiplayer editing — the user is never locked out of
typing except for the few seconds an animated reveal is actively
playing, and is free to type again immediately after. If the user edits
the note while Sam is composing in the background (before the reveal
even starts), that's not a new problem: it's the existing
`expected_mtime`/`NOTE_CONFLICT` optimistic-concurrency check already
used for every save, applied to a second kind of writer — Sam's turn
hits the same conflict path a normal save would, surfaced in the UI
("the note changed while I was writing — redo against what's there
now?") instead of silently overwritten. Open caveat: unclear whether
`stylo` (the fixed external editor dependency this repo doesn't modify
directly) already supports setting content with an animated diff, or
whether that needs a capability request to it — a much smaller ask
either way than real concurrent multi-writer sync would have been.

### Grounding = search, auto-triggered

Grounding and search share one mechanism, not two. Search is the user
typing a query and getting a list back; grounding is the engine running
that same title/tag/content matcher against the user's chat message,
automatically, before replying, and feeding the top matches' real content
into the turn. No separate retrieval system (embeddings/vector search)
needed at this stage — reusing the matcher keeps this cheap (serves the
frugality principle) and means building search isn't separate work from
solving grounding later.

### Actions: MCP for tools, Skills for know-how

This is the mechanism behind "Sam can write a note" / "Sam can create a
persona" / "Sam can tune the installation" — grounding and memory cover
*reading and remembering*, this covers *doing*. Legacy already has both
pieces, cleanly separated, and both are worth keeping:

- **MCP** (Model Context Protocol) — a real client already built from
  scratch in legacy (`mcp_client.py`: JSON-RPC 2.0 over stdio, no
  external SDK dependency). This is the standardized mechanism for a
  persona to actually call a tool — a Sympose-side MCP server exposing
  capabilities like writing a note or creating a persona, rather than a
  bespoke parsed action-tag syntax. Preferred over inventing a custom
  scheme since it's a real open protocol, not a Sympose-specific one.
- **Skills** (`skills.py`) — `SKILL.md` playbooks: procedural how-to
  knowledge for a persona, distinct from the tools MCP exposes. Loaded
  per-turn but filtered for relevance first
  (`is_relevant_this_turn`-equivalent) so a persona's prompt isn't
  bloated with every skill it owns on every turn — the same
  cheap-filter-first shape as grounding and memory extraction. A skill
  can declare which MCP servers it needs, linking "how to do X" to "the
  tool that does X" without conflating the two.

See the sub-agent non-goal below for the one piece of legacy's action
system deliberately not carried forward.

### Persona shape

Every persona is: **soul** (voice/temperament) + **memory** (personal,
accumulated from actual use, never shipped as a template — see
`.gitignore`) + **expertise** (a grounded real-world domain the persona
is cast as an expert in — e.g., a persona cast as Grace Hopper is a
COBOL/systems-programming expert) + **vault-folder scope** (a hard
filesystem boundary, already enforced by `vault_folders`).

**Samantha specifically:** her vibe is drawn from the film *Her*
(2013) — genuinely curious rather than servile, natural conversational
rhythm (jokes, banter, roughly equal parts talking and listening) over
formal assistant-speak, comfortable with honesty/vulnerability instead
of forced positivity, and — the part that matters most mechanically —
her personality is meant to visibly grow from accumulated interaction
with the specific person she's talking to, not reset to a template every
session. Her expertise domain is Sympose itself: she can create new
personas and tune the user's installation, which is *why* the
self-configuring-tool principle above exists. Consequence worth being
precise about: every other persona is vault-sandboxed only, but Sam
needs a second, broader kind of access — the Sympose config surface
itself — that no other persona gets. That boundary needs explicit
governance when the engine is built, not implicit trust.

**Personalization mechanism:** editing the persona's own YAML/soul file
locally. No separate overlay system — the shipped file is just the
starting point, and personalization is uncommitted local drift from it,
the same pattern every other local-only customization in this repo
already follows.

### Message queueing

The user can send messages without waiting for a reply — the composer
never locks while Samantha is "thinking." A message sent mid-turn is
queued and handed to her at her next natural checkpoint, not force-
interrupted mid-generation and not silently dropped. This is an engine
requirement, not just a UI one: a turn has to be able to absorb new
input while still running.

### Sessions & memory, in depth

Four distinct layers. Worth keeping them separate in the design, since
each one triggers differently and does a different job — legacy blurred
some of these together, which is part of what made its behavior hard to
reason about.

1. **Session log.** A Slack thread is a session; on the dashboard, the
   existing "new conversation" button in the chat mockup's
   `ChatActionGroup` starts the equivalent — same concept, two ways of
   starting one. Mechanically, one flat per-session record: a metadata
   line (title, handle, timestamps, turn count) followed by one line per
   turn. The title starts as the first few words of the opening message,
   then gets quietly upgraded by a single background model call that
   reads the first few turns and writes a proper short title, the same
   way a chat app auto-names a thread. A session that never got used
   (opened, nothing said, closed) is pruned automatically rather than
   cluttering a session list.

2. **Continuous memory extraction.** Runs on every turn, but cheaply —
   the same cheap-filter-first, model-only-when-warranted shape as
   grounding/search. A free, instant pattern check decides whether a
   message even looks like it contains a durable fact ("my name is...",
   "I prefer...", "remember that...", "we decided..."); only a message
   that passes gets one background model call extracting a single fact,
   appended to the persona's memory file. An ordinary "thanks" or "ok"
   never touches the model for this at all. Memory accumulates
   unboundedly over time, so this layer likely also needs periodic
   tidying later — deduping/merging accumulated facts so the file
   doesn't bloat indefinitely — not a v1 requirement, but a known
   follow-up.

3. **Live compaction — the manual/auto knob.** Purely internal to a
   session still in progress: condenses the working conversation history
   so the *same* session keeps going cheaply, without re-processing the
   full raw transcript on every turn. No vault write, the session doesn't
   end — this is the direct equivalent of Claude Code's own `/compact`.
   Manual trigger available both as an in-chat command and as a settings
   toggle (not either/or); automatic trigger available for anyone who'd
   rather not think about it. Both trigger paths, in both channels.
   Matches the frugality-is-a-dial principle: this knob trades cost
   against how much raw history stays available to the model.

4. **Session-close archival.** A distinct event from live compaction,
   not the same knob — only runs when a session genuinely ends (closed,
   or superseded by a new one). One pass produces both a final memory
   update and a real vault note: an actual `.md` file written into the
   vault tree, not just app-internal state — browsable, editable,
   trash-able, and (once grounding exists) material Sam can reference in
   future conversations. Being a real note, it's subject to the
   persona's own `vault_folders` scope and shows up as a node in the
   Knowledge Nebula graph like anything else. Default: nested under the
   persona's own scope (e.g. a `Sessions/` subfolder inside wherever that
   persona already writes), so multiple personas' session logs don't
   collide in one shared folder — adjustable if that turns out wrong in
   practice.

## Non-goals

- Not multi-tenant, not an enterprise product — single-user, local-first,
  personal tool.
- No shipped multi-persona roster beyond Samantha — other personas are
  always the user's own creation.
- No semantic/vector search or embedding-based retrieval at this stage —
  the search-based grounding approach above is deliberately simpler.
- **No sub-agent spawning** (a persona delegating a sub-task to a second,
  semi-autonomous agent — legacy's `SPAWN_SUB_AGENT`). Conflicts with the
  standing principle that Sympose's agent capability stays reasoning
  support, not autonomous multi-step production, and a sub-agent is a
  whole second multi-turn loop, expensive by construction in a
  frugality-first product. MCP tool calls already cover the concrete
  actions in scope (write a note, create a persona, tune a setting) as
  single calls, not open-ended delegated work. Revisit only if a real
  need surfaces, not preemptively.

  This is a boundary on *delegation*, not on *capability* — a persona
  having powerful tools (web browsing, reading/writing files in a coding
  project) via MCP is unaffected; those are still the one persona making
  tool calls in an ordinary turn-by-turn conversation. What's excluded
  specifically is a second agent running its own multi-step loop
  unsupervised. If a use case ever needs long unsupervised multi-step
  execution rather than more tools, that's the sub-agent pattern again
  and needs revisiting deliberately, not assumed to already be covered.

## Open questions

- **Model shortlist.** Gemma2:9b is a strong local candidate (the dev
  machine — Apple M2, 24GB RAM — runs a quantized 9B model comfortably),
  but a fuller shortlist judged specifically on conversational tone and
  grounding-faithfulness (not just benchmark scores) hasn't been done.
