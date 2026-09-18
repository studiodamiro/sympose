---
title: "ADR-130 — Streaming Persona Chat Endpoint (SSE) & Structured Action Events"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - sympose/dashboard
---

# ADR-130 — Streaming Persona Chat Endpoint (SSE) & Structured Action Events

- **Status:** Implemented (backend). Frontend wiring is ADR-131.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Scoping the originally-separate "external bot ingress" endpoint (a plain
POST for a widget/webhook to message a persona) led to a broader question:
could Sympose's own dashboard get Claude-Code-style real-time visibility —
watching a reply stream in, watching each action the persona takes appear
as its own visible event? Investigating found the dashboard's chat UI
(`ui/src/components/sympose/chat-panel.tsx`, `chat-message.tsx`,
`action-badge.tsx`) is fully built but wired to nothing — no fetch, no
websocket, and `server.py` had zero chat-capable route at all. The wiki's
own dashboard spec (`docs/wiki/architecture/dashboard-and-vault-explorer.md`)
documents this exact UX (an inline `> 📝 Action: Note saved to Vault` row)
as a design mockup that was never built. damiro confirmed combining the two:
one streaming endpoint serves both the dashboard's live chat and external
bot/widget ingress, since both are "send a persona a message, get a live
reply," and he confirmed the dashboard's own **Engine First, Face Second**
principle (already documented) stays intact, and that terminal-only usage
must remain fully unaffected (it is — nothing here touches the terminal's
own code path, which never loads `server.py`).

Two technical constraints ruled out WebSocket in favor of Server-Sent
Events, discovered by reading the actual installed dependencies and
middleware rather than assuming:

- The installed `uvicorn` has neither `websockets` nor `wsproto` — a
  WebSocket route needs one of those, which would need its own ADR under
  the no-new-dependencies rule.
- `DashboardAuthMiddleware` only guards `scope["type"] == "http"`,
  passing every WebSocket handshake through unauthenticated today; a
  browser also can't set a Basic-Auth header on a WS upgrade request
  anyway, so a WS endpoint would need an entirely new auth mechanism.

SSE is a normal HTTP response, so the *existing* auth middleware and CORS
setup already cover it with zero new code, and `StreamingResponse` is
native to Starlette/FastAPI — zero new dependencies either way. The
interaction (one message in, one streamed reply out) is naturally
one-directional, which also fits SSE better than WebSocket's bidirectional
model.

A third finding shaped the event design: `action-badge.tsx`'s `ActionBadge`
component already expects a structured `{action: ActionKind, detail?:
string}` shape — the frontend contract for this feature already existed
and had simply never been fed real data.

## Decision

**Backend action-event plumbing (`sympose/actions.py`,
`engine_turn_grounding.py`, `engine_turn_pipeline.py`):**
- `_ActionContext` gains an optional `on_action: Callable[[dict[str, str]],
  None] | None = None` field, mirroring the existing `on_progress` field's
  contract exactly.
- At each of the 8 action-tag success paths whose tag name matches
  `ActionBadge`'s `ActionKind` union — `WRITE_NOTE`, `APPEND_NOTE`,
  `DAILY_NOTE`, `SEARCH`, `SPAWN_SUB_AGENT`, `CONFIG_SET`,
  `CREATE_PERSONA`, `DELETE_PERSONA` — one `if ctx.on_action:
  ctx.on_action({"action": ..., "detail": ...})` call sits alongside the
  existing `ctx.badges.append(...)` call. The `detail` value is always a
  variable already in scope at that call site (`rel_path`, `key`,
  `f"@{h_name}"`, the search `query`, `badge_spec`) — no parsing of the
  formatted badge markdown string. Failure/warning paths (e.g. `WRITE_NOTE`
  failing, `SEARCH` returning nothing) do **not** fire `on_action` —
  `ActionBadge` has no error variant, so only completed actions are
  reported. Tags with no frontend `ActionKind` counterpart (`REMEMBER`,
  `READ_NOTE`/`VIEW_NOTE`, `WEB_SEARCH`, `WRITE_CANVAS`, `REACT`) are
  unchanged — `WEB_SEARCH` in particular was deliberately not remapped
  onto the `SEARCH` kind; that would be inventing a mapping the frontend
  spec doesn't actually make.
- `execute_actions(..., on_action=None)` threads it into `_ActionContext`
  and into the one-level recursive re-invocation `SPAWN_SUB_AGENT` makes on
  a sub-agent's own synthesis text, so a nested action inside a sub-agent's
  output also surfaces.
- `_apply_grounding_and_stream_result(..., on_action=None)` and
  `chat_stream(..., on_action=None)` thread it the rest of the way up,
  including into the runtime-injected forced-retrieval `execute_actions`
  call the strict-grounding path makes on its own.
- Every new parameter defaults to `None`; every existing caller (`cli.py`,
  `slack.py`) is unchanged — confirmed by the full test suite staying
  green throughout with zero test modifications needed for existing tests.

**New `sympose/server_chat.py`** (123 lines): `POST /api/chat/stream`,
body `{persona, text, session_id?, source="dashboard"}`. Registered in
`create_app` alongside the other route groups — **no enable/disable knob**:
protected by the same `DashboardAuthMiddleware` every route already has,
so it's simply available whenever the dashboard runs (Engine First, Face
Second — chat is core, not an optional bolt-on). `stream_chat_events`
wraps `engine.chat_stream(...)`, forwarding text chunks as `event: text`,
mapping the `"CLEARED_SESSION"` sentinel to `event: cleared`, draining an
`on_action`-populated queue into `event: action` frames after each
generator step (deterministic ordering — single-threaded generator
execution, not real concurrency), and always closing with `event: done`.
`session_id` composes as `f"chat:{source}:{session_id or 'default'}"`,
the same shape as Slack's `f"{thread_id}:{handle}"`; `source` is a
session-keying label only, never an authorization boundary (anyone who
can authenticate to the dashboard can call this, same trust model as
every other route today).

**A bug my own tests caught before it shipped**: `_sse_frame`'s first
draft special-cased a plain string as raw, un-encoded `data:` content. A
model's streamed reply chunk containing a literal newline (routine for
multi-line text) would have corrupted the SSE frame, since `data:` lines
are themselves newline-delimited. Fixed to JSON-encode every event's
payload unconditionally, including plain text — caught by
`test_multiline_text_chunk_stays_json_encoded_not_raw` before this reached
any real usage.

**Deliberately not solved here**: the backend forwards text chunks
verbatim, badge markdown included, even though the same information now
also arrives as a structured `action` event — no attempt is made to strip
the inline `"> 📝 ..."` badge text out of the stream. Guessing which chunk
is "the badge block" from inside a generic wrapper would be fragile (and
wrong for an ordinary reply that happens to start with a blockquote).
That reconciliation belongs in ADR-131's frontend, which can inspect text
line-by-line far more safely than this module can.

**Honest limitation carried forward, not solved**: actions still don't
execute mid-generation — `chat_stream` streams the model's full raw reply
first, *then* runs `execute_actions` once. What a client sees is: the
reply streaming in, then each completed action arriving as its own event,
then any closing synthesis text — not truly interleaved token-by-token
execution. Still a large, real improvement over today's one-flat-blob
experience in both the terminal and Slack, and disclosed rather than
implied to be more than it is.

## Consequences

**Positive**
- 27 new tests (13 for `on_action` threading across all 8 tag types plus
  the recursive sub-agent case, 11 for `stream_chat_events`'s SSE framing,
  3 end-to-end through the real ASGI app including auth) — full suite:
  1121 passed, 0 regressions.
- The end-to-end route test confirms the auth story directly: an
  unauthenticated `POST /api/chat/stream` gets 401, same as every other
  dashboard route — no WebSocket-shaped gap was introduced because none of
  this uses a WebSocket.
- Zero new dependencies, zero new auth code, zero change to any existing
  `chat_stream`/`execute_actions` caller.

**Negative / costs**
- The dashboard's chat UI is still not actually wired to this endpoint —
  that's ADR-131. This ADR is inert from a user's perspective until then.
- `actions.py` grew by ~30 lines (781 → 810) — still over the 200-LOC
  guidance, pre-existing debt this ADR didn't set out to fix, consistent
  with the "thin wiring only" strategy for already-oversized files.

## Alternatives rejected

- **WebSocket instead of SSE.** Rejected — needs a new dependency
  (`websockets`/`wsproto`) and a new auth mechanism (the existing
  middleware doesn't guard WS scope, and browsers can't set Basic-Auth
  headers on a WS handshake). SSE needed neither.
- **A separate `server.ingress_enabled` knob gating this route.**
  Rejected — the route is already behind the same password every other
  dashboard route uses; a second toggle would just be an extra thing to
  misconfigure for no added safety, and conflicts with treating chat as
  core dashboard functionality rather than an optional extra.
- **Stripping the badge markdown out of forwarded text chunks in this
  module.** Rejected — see Decision; no reliable way to identify "this is
  the redundant part" from a generic string-chunk wrapper without real
  risk of also eating a legitimate reply.
- **Remapping `WEB_SEARCH` onto the frontend's `SEARCH` `ActionKind`.**
  Rejected as an unrequested assumption — the frontend spec defines
  exactly one search kind; inventing the mapping direction wasn't this
  ADR's call to make silently.
