"""The CLI app's run-time state (docs/decisions/008): which model and panel are active, the
session, one lock per persona, and the counters that decide whether a turn is in flight.
Set up once from `SymposeCLI.on_mount`; split out of `app.py` to hold the 200-line cap."""

import asyncio

from sympose.cli.selection import SelectionPanel


def init(app) -> None:
    # `None` until `/model` picks one, so a persona's own model (or the
    # `chat_model` setting) applies — see `mock_data.active_model`.
    app.model_override = None
    app.panel: SelectionPanel | None = None
    app.panel_kind: str | None = None
    # One session per CLI process run — the engine starts a new one on
    # the first real turn; `/clear` wipes the visible transcript only,
    # it does not reset this (no `/new`-style command exists yet).
    app.session_id: str | None = None
    # Bumped every time `session_id` is deliberately reset (a persona
    # switch), so a call still in flight then must not write its own
    # now-stale session_id back once it resolves. The persona handle
    # alone isn't enough: switching away and back to the *same* persona
    # would restore a matching handle with a stale session_id anyway.
    app.session_generation = 0
    # The session id each generation actually resolved to, so a queued
    # message for the same persona/generation can continue it even if
    # an unrelated persona switch has since reset `session_id` itself
    # (docs/decisions/008). `session_id` above stays a convenient
    # mirror of the *current* generation's entry here.
    app.session_by_generation: dict[int, str | None] = {}
    # One lock per persona handle (docs/decisions/008), not a single
    # global one: sessions are stored per-handle
    # (sympose/engine/session.py), so two different personas' turns
    # never touch the same file and never actually race each other —
    # only two turns for the *same* persona need to queue behind one
    # another. The composer itself is never blocked either way.
    app.turn_locks: dict[str, asyncio.Lock] = {}
    # Every currently-streaming reply's own timer — not a single slot,
    # since turns for different personas (or two queued same-persona
    # turns) can now genuinely stream concurrently post-lock.
    app.active_reply_timers: set = set()
    # A plain counter, not `turn_locks[...].locked()`, for "is any turn
    # genuinely in flight right now" (docs/decisions/008): incremented
    # the instant `send_message` starts and decremented only once it's
    # fully done, covering the *whole* call including any time spent
    # queued. `Lock.locked()` is a point-in-time snapshot that briefly
    # reads `False` in the gap between one queued call releasing the
    # lock and the next one resuming to re-acquire it — a real, if
    # narrow, window where `/quit` could wrongly take the graceful
    # path and reproduce the exact hang this mechanism exists to
    # prevent (an already-running blocking call can't be cancelled).
    app.pending_turns = 0
    # Tab/Shift+Tab cycle-and-fill state for the `/`-autocomplete
    # overlay (see `composer.py`/`picker.py`); `None` means no
    # cycle session is active (last edit was real typing, not Tab).
    app.tab_matches = None
    app.tab_index = -1
    app.filling_tab_count = 0
    # Which "chatter" (user / persona / system) mounted the last line:
    # `transcript.py`'s `mount_line` only adds a gap above a line when
    # this changes, so consecutive lines from one speaker stay grouped.
    app.last_speaker: str | None = None
