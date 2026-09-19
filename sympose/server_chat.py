"""
Streaming Persona Chat Endpoint for Sympose's Dashboard (ADR-130).

`POST /api/chat/stream` is the one thing the dashboard needed that didn't
exist before: a way to send a persona a message and watch the reply arrive
live, action-by-action, instead of one flat blob after the fact. The same
endpoint also serves external bot/widget ingress (a desktop widget, a
webhook) — both are "send a persona a message, get a live reply," so this
is one mechanism, not two.

Server-Sent Events, not WebSocket: SSE is a normal HTTP response
(`scope["type"] == "http"`), so the *existing* `DashboardAuthMiddleware`
(which only guards HTTP scope) already protects this route with zero new
code, and it needs zero new dependencies — `StreamingResponse` is native
to Starlette/FastAPI, already installed. A WebSocket route would need
`websockets`/`wsproto` (neither installed) and its own auth path (browsers
can't set Basic-Auth headers on a WS upgrade request). The interaction is
naturally one-directional anyway — one message in, one streamed reply out.

Honest limitation, not hidden: actions don't execute mid-generation today
— `PersonaEngine.chat_stream` streams the model's full raw reply first,
*then* runs `ActionProcessor.execute_actions` once. What a client actually
sees is: the reply streaming in, then each completed action arriving as
its own event, then any closing synthesis text. `chat_stream`'s new
`on_action` parameter (ADR-130) is what makes the "own event" part
possible without changing that execution order.

Text chunks are forwarded verbatim, badge markdown included — this module
does not try to strip the inline "> 📝 ..." badge text out of the stream
just because the same information is also being sent as a structured
`action` event. Guessing which chunk is "the badge block" from in here
would be fragile (and wrong for an ordinary reply that happens to start
with a blockquote). Reconciling the two — e.g. a frontend choosing not to
render lines that start with "> " in the message body, since the footer's
action badges already cover that — is a presentation decision that
belongs where the text is easy to inspect line-by-line: the frontend.
"""

import json
import logging
from collections import deque
from collections.abc import Generator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class ChatMessageIn(BaseModel):
    """Body of `POST /api/chat/stream`."""

    persona: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    session_id: str | None = None
    # Labels the caller for session-keying only ("dashboard", a widget's own
    # name, ...) — never an authorization boundary. The dashboard password
    # guard is what actually gates this endpoint, same as every other route.
    source: str = "dashboard"


def _sse_frame(event: str, data: Any) -> str:
    """Always JSON-encodes `data`, even a plain string — SSE's `data:` line
    is newline-delimited, so an un-encoded multi-line text chunk (routine
    for a model's streamed reply) would silently corrupt the frame. The
    frontend JSON-decodes every event's data uniformly as a result."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _compose_session_id(source: str, session_id: str | None) -> str:
    """Same shape as Slack's `f"{thread_id}:{handle}"` session keying."""
    return f"chat:{source}:{session_id or 'default'}"


def stream_chat_events(
    engine: Any, handle: str, text: str, session_id: str
) -> Generator[str, None, None]:
    """Wraps `engine.chat_stream` into SSE frames: each model text chunk as
    `event: text`, each completed action as its own `event: action` (queued
    by the `on_action` callback and drained after every generator step —
    correct because this is single-threaded generator execution, not real
    concurrency, so the ordering is deterministic), the existing
    `"CLEARED_SESSION"` sentinel as its own `event: cleared` instead of
    literal text, and a final `event: done`."""
    queued_actions: deque[dict[str, str]] = deque()

    def _capture_action(event: dict[str, str]) -> None:
        queued_actions.append(event)

    stream = engine.chat_stream(
        handle, text, session_id=session_id, on_action=_capture_action
    )
    for chunk in stream:
        while queued_actions:
            yield _sse_frame("action", queued_actions.popleft())
        if chunk == "CLEARED_SESSION":
            yield _sse_frame("cleared", {})
            continue
        yield _sse_frame("text", chunk)
    while queued_actions:
        yield _sse_frame("action", queued_actions.popleft())
    yield _sse_frame("done", {})


def _post_chat_stream(engine: Any, body: ChatMessageIn) -> StreamingResponse:
    session_id = _compose_session_id(body.source, body.session_id)
    return StreamingResponse(
        stream_chat_events(engine, body.persona, body.text, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Disables response buffering on nginx-style reverse proxies so
            # chunks actually arrive incrementally instead of all at once.
            "X-Accel-Buffering": "no",
        },
    )


def register_chat_routes(app: FastAPI, engine: Any) -> None:
    @app.post("/api/chat/stream")
    def post_chat_stream(body: ChatMessageIn) -> StreamingResponse:
        return _post_chat_stream(engine, body)
