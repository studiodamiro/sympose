"""What actually happens once a command or message is dispatched: mock
slash-command behavior (still canned — no session/history data model
exists yet), and a real chat reply from the engine "streaming" into the
transcript via a repeating timer — the one piece worth previewing live
above all else, since it's the thing legacy's blocking input loop
couldn't do."""

import asyncio
import concurrent.futures
import logging
import os

from rich.style import Style
from rich.text import Text

from sympose import engine
from sympose.cli import picker, transcript as transcript_mod
from sympose.cli.commands import COMMANDS
from sympose.cli.mock_data import MOCK_HISTORY, MOCK_MODELS, list_personas
from sympose.cli.selection import SelectionOption

log = logging.getLogger(__name__)

# A dedicated executor for engine calls, not asyncio's own loop-default one
# `asyncio.to_thread` would use — `asyncio.run()`'s shutdown sequence
# specifically waits for the *default* executor to drain, which would hang
# `/quit` for up to a model call's whole timeout if one were still in
# flight (see `__main__.py`'s `os._exit`, the other half of this fix).
# Uncancellable once started either way (a thread blocked in a network
# call can't be interrupted from outside), so this only changes whether
# quitting has to wait for it.
_ENGINE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="sympose-engine"
)


def _force_exit() -> None:
    """A thin wrapper around `os._exit` — never called directly inline, so
    tests can monkeypatch this one function instead of the real call
    actually terminating the test process."""
    os._exit(0)  # pragma: no cover - exercised via the monkeypatched stub in tests


def _show_failure(app, transcript, message: str) -> None:
    """`/quit` fired while this call was in flight — `_exit` is a
    private/underscore Textual attribute, not part of its public API, but
    the only signal available for that; worth a test catching a future
    Textual upgrade that renames/removes it rather than this silently
    becoming a no-op (see `tests/test_cli.py`'s quit-while-in-flight
    test)."""
    if app._exit:
        return
    transcript_mod.mount_line(app, f"Sam couldn't reply: {message}", "system")
    transcript.scroll_end(animate=False)


async def run_command(app, command) -> None:
    transcript = app.transcript
    if command.name == "/help":
        transcript_mod.mount_line(app, "Commands:", "system")
        for c in COMMANDS:
            color = app.theme_color("error", "red") if c.danger else app.theme_color("primary", "cyan")
            line = Text()
            line.append(f"  {c.name:<10}", style=Style(color=color, bold=True))
            line.append(c.summary)
            transcript_mod.mount_line(app, line, "system")
    elif command.name == "/model":
        await picker.open_picker(
            app, "model", "Select a model", [SelectionOption(m.label, m.id) for m in MOCK_MODELS]
        )
    elif command.name == "/persona":
        await picker.open_picker(
            app,
            "persona",
            "Select a persona",
            [
                SelectionOption(f"{p.name} — {p.title}" if p.title else p.name, p.handle)
                for p in list_personas()
            ],
        )
    elif command.name == "/history":
        await picker.open_picker(
            app, "history", "Recent conversations", [SelectionOption(e, e) for e in MOCK_HISTORY]
        )
    elif command.name == "/compact":
        transcript_mod.mount_line(app, "Conversation compacted (mock) — nothing to trim yet.", "system")
    elif command.name == "/clear":
        # A reply may still be mid-stream — stop its timer rather than
        # let it keep ticking against a transcript that was just
        # cleared out from under it (it would otherwise keep updating
        # a detached widget and scrolling the transcript for up to the
        # rest of the reply's length).
        if app.reply_timer is not None:
            app.reply_timer.stop()
            app.reply_timer = None
        await transcript.remove_children()
        app.last_speaker = None
    elif command.name == "/settings":
        # No dashboard-style Settings page exists in a terminal, so unlike
        # the dashboard's `/settings` (wired to real navigation), this
        # stays inert-by-default.
        transcript_mod.mount_line(
            app, "Settings aren't available in the CLI yet — this is a mock.", "system"
        )
    elif command.name == "/quit":
        # `app.action_quit` (also Textual's own ctrl+q/command-palette
        # quit route) has the turn_lock-aware fast-exit check — one place
        # for it, not duplicated here too.
        await app.action_quit()
        return
    transcript.scroll_end(animate=False)


def apply_picker_choice(app, kind: str, value: str | None) -> None:
    transcript = app.transcript
    if kind == "model":
        model = next((m for m in MOCK_MODELS if m.id == value), None)
        if model is not None:
            app.model = model
            picker.update_banner(app)
            transcript_mod.mount_line(app, f"Switched model to {model.label}.", "system")
    elif kind == "persona":
        persona = next((p for p in list_personas() if p.handle == value), None)
        if persona is not None and persona.handle != app.persona.handle:
            app.persona = persona
            # Sessions are stored per-handle (sympose/engine/session.py) — an
            # old session_id from the previous persona would resolve to a
            # different persona's directory under the new handle (nothing
            # there, silently empty history) while still writing new turns
            # under the old id, forking/losing history across the switch.
            # A new persona starts a fresh session, same as a fresh process.
            app.session_id = None
            app.session_generation += 1
            picker.update_banner(app)
            transcript_mod.mount_line(app, f"Now talking to @{persona.handle}.", "system")
    elif kind == "history":
        transcript_mod.mount_line(
            app, "History browsing isn't wired up yet — this is a placeholder.", "system"
        )
    transcript.scroll_end(animate=False)


async def send_message(app, value: str) -> None:
    transcript = app.transcript
    line = Text()
    line.append("You  ", style=Style(bold=True, dim=True))
    line.append(value)
    transcript_mod.mount_line(app, line, "user")
    transcript.scroll_end(animate=False)

    # Captured now, not re-read after the await below: the lock only
    # serializes the engine call itself, so persona/model can change (via
    # `/persona`/`/model`) — or the app can start exiting (`/quit`) —
    # while this call is still in flight. The reply must stay attributed
    # to whoever actually generated it, not whatever's current by the time
    # it resolves, and a stale session_id must never be written back over
    # a session the user has since switched away from. `session_generation`
    # (not just the persona handle) guards the session_id write below —
    # switching away and back to the *same* persona before this call
    # resolves would still match on handle alone, but must still be
    # treated as stale, since the second switch's reset is what should win.
    handle = app.persona.handle
    model_id = app.model.id
    reply_header = f"@{handle} · {app.model.short}"
    session_generation = app.session_generation

    # The lock serializes the engine call itself, not the composer — the
    # user can keep typing and submitting; a message sent while another is
    # still in flight simply waits its turn here rather than racing it for
    # `app.session_id` and the session file (docs/decisions/006). The
    # actual model call is offloaded to a thread inside the lock — running
    # it directly on Textual's single-threaded event loop would freeze the
    # persistent input for the whole round-trip, exactly what this CLI
    # exists to avoid.
    async with app.turn_lock:
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                _ENGINE_EXECUTOR, engine.run_turn, handle, value, app.session_id, model_id
            )
        except engine.EngineModelError as e:
            _show_failure(app, transcript, str(e))
            return
        except Exception as e:
            # Anything other than EngineModelError is a bug somewhere in
            # the engine pipeline (grounding/prompt/session), not an
            # expected failure mode — still degrade to an in-transcript
            # line rather than letting it crash the whole app, the same
            # as every other failure path here.
            log.warning("Unexpected error during a turn: %s", e)
            _show_failure(app, transcript, f"unexpected error ({e}).")
            return
        if app._exit:  # /quit fired while this call was in flight
            return
        if app.session_generation == session_generation:  # no reset since dispatch
            app.session_id = result.session_id

    _stream_reply(app, result.reply, reply_header)


def _stream_reply(app, reply: str, header: str) -> None:
    transcript = app.transcript
    accent = app.theme_color("accent", "cyan")
    reply_widget = transcript_mod.mount_line(app, "", "persona")
    words = reply.split(" ")
    shown = {"count": 0}

    def tick() -> None:
        # Defensive: the widget can be gone before the timer is (e.g. a
        # teardown path that doesn't go through `/clear`'s explicit
        # `app.reply_timer.stop()`), so bail rather than update/scroll a
        # detached widget.
        if not reply_widget.is_mounted:
            timer.stop()
            return
        shown["count"] += 1
        body = " ".join(words[: shown["count"]])
        done = shown["count"] >= len(words)
        text = Text()
        text.append(header + "\n", style=Style(color=accent, bold=True))
        text.append(body + ("" if done else " ▋"))
        reply_widget.update(text)
        transcript.scroll_end(animate=False)
        if done:
            timer.stop()
            app.reply_timer = None

    timer = app.set_interval(0.05, tick)
    app.reply_timer = timer
