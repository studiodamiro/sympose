"""Dispatching a chat message to the engine and streaming its reply back
into the transcript — including message queueing (docs/decisions/008):
one `asyncio.Lock` per persona handle, so turns for the same persona stay
strictly ordered (they'd race the same session file otherwise) while
turns for different personas can run concurrently (different files, no
collision). Split out of `runtime.py` to hold the 200-LOC-per-file cap
(docs/decisions/006 flagged this as deferred follow-up)."""

import asyncio
import concurrent.futures
import logging

from rich.style import Style
from rich.text import Text

from sympose import engine
from sympose.cli import grounding_line, meter, share, trim_notice
from sympose.cli import transcript as transcript_mod
from sympose.cli.mock_data import active_model

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


def _show_failure(app, transcript, handle: str, message: str) -> None:
    """`/quit` fired while this call was in flight — `_exit` is a
    private/underscore Textual attribute, not part of its public API, but
    the only signal available for that; worth a test catching a future
    Textual upgrade that renames/removes it rather than this silently
    becoming a no-op (see `tests/test_cli.py`'s quit-while-in-flight
    test)."""
    if app._exit:
        return
    # A `Text`, not a string: the message comes from a provider, and a string is read as markup
    # (a `[/foo]` in it would stop the app when the line is drawn).
    transcript_mod.mount_line(app, Text(f"@{handle} couldn't reply: {message}"), "system")
    transcript.scroll_end(animate=False)


def _record_session_result(app, generation: int, session_id: str) -> None:
    app.session_by_generation[generation] = session_id
    if generation == app.session_generation:  # still the live conversation
        app.session_id = session_id


def _queued_text(base: Text) -> Text:
    text = base.copy()
    text.append("  · queued", style=Style(dim=True, italic=True))
    return text


async def send_message(app, value: str) -> None:
    # Counts this call for the *whole* time it's alive, including any time
    # spent queued behind another turn for the same persona — not just
    # while its own engine call is running. `action_quit` (app.py) checks
    # this instead of a lock's `.locked()`, which is a point-in-time
    # snapshot that can briefly read `False` in the gap between one queued
    # call releasing its persona's lock and the next one resuming to
    # re-acquire it (docs/decisions/008).
    app.pending_turns += 1
    try:
        await _send_message(app, value)
    finally:
        app.pending_turns -= 1


async def _send_message(app, value: str) -> None:
    transcript = app.transcript
    line = transcript_mod.styled_line("You  ", Style(bold=True, dim=True), value)
    user_widget = transcript_mod.mount_line(app, line, "user")
    transcript.scroll_end(animate=False)

    # Captured now, not re-read after the await below: a persona/model
    # switch, or `/quit`, can happen while this call is still in flight.
    # The reply must stay attributed to whoever actually generated it, and
    # a stale result must never be written back over state the user has
    # since moved on from. `generation` (not just the persona handle)
    # guards the writes below — switching away and back to the *same*
    # persona before this call resolves would still match on handle alone,
    # but must still be treated as stale, since the second switch's reset
    # is what should win.
    handle = app.persona.handle
    # `None` when the user hasn't picked one with `/model`: the engine then
    # applies the persona's own model / the setting / the default itself
    # (docs/decisions/010), and `active_model` shows that same resolution.
    model_id = app.model_override.id if app.model_override else None
    reply_header = f"@{handle} · {active_model(app.persona, app.model_override).short}"
    generation = app.session_generation
    meter_epoch = meter.epoch(app)  # a model or persona switch meanwhile makes the figure stale

    # One lock per persona (docs/decisions/008), not one global lock:
    # sessions are stored per-handle (sympose/engine/session.py), so two
    # different personas' turns never touch the same file and never
    # actually race each other — only two turns for the *same* persona
    # need to queue behind one another. The composer itself is never
    # blocked either way; a message just waits its turn here if its
    # persona's lock is already held.
    lock = app.turn_locks.setdefault(handle, asyncio.Lock())
    was_queued = lock.locked()
    if was_queued:
        user_widget.update(_queued_text(line))

    async with lock:
        if was_queued:
            user_widget.update(line)  # clear the "queued" marker

        # Deliberately not `app.session_id` read live: that single slot can
        # be reset by an unrelated persona switch that bumped
        # `session_generation` in between, orphaning a queued message onto
        # a fresh session instead of the one it should continue
        # (docs/decisions/008).
        session_id = app.session_by_generation.get(generation)
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                _ENGINE_EXECUTOR, engine.run_turn, handle, value, session_id, model_id
            )
        except engine.EngineModelError as e:
            _show_failure(app, transcript, handle, str(e))
            return
        except Exception as e:
            # Anything other than EngineModelError is a bug somewhere in
            # the engine pipeline (grounding/prompt/session), not an
            # expected failure mode — still degrade to an in-transcript
            # line rather than letting it crash the whole app, the same
            # as every other failure path here.
            log.warning("Unexpected error during a turn: %s", e)
            _show_failure(app, transcript, handle, f"unexpected error ({e}).")
            return
        if app._exit:  # /quit fired while this call was in flight
            return
        _record_session_result(app, generation, result.session_id)

    meter.show(app, result.context_used, result.context_limit, meter_epoch)
    if result.ttft_ms is not None:
        reply_header += f" · TTFT {_format_ttft(result.ttft_ms)}"
    reply_header += trim_notice.segment(result.history_dropped, result.truncated)
    reply_header += share.header_segment(result.cloud, result.withheld)  # before the notes, which fit the room left
    reply_header += grounding_line.header_segment(
        reply_header, result.grounding, app.size.width, result.searched
    )
    _stream_reply(app, result.reply, reply_header)
    if not result.saved:
        # The reply was given, but it is not in the conversation file (the log has the reason), so a
        # later message will not remember it; saying so here is the only place the user looks.
        transcript_mod.mount_line(
            app, Text(f"@{handle}'s reply was not saved: the conversation file could not be written."), "system"
        )
        transcript.scroll_end(animate=False)


def _format_ttft(ms: int) -> str:
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f}s"


def _stream_reply(app, reply: str, header: str) -> None:
    transcript = app.transcript
    accent = app.theme_color("accent", "cyan")
    reply_widget = transcript_mod.mount_line(app, "", "persona")
    words = reply.split(" ")
    shown = {"count": 0}

    def _finish() -> None:
        timer.stop()
        app.active_reply_timers.discard(timer)

    def tick() -> None:
        # Defensive: the widget can be gone before the timer is (e.g. a
        # teardown path that doesn't go through `/clear`'s explicit stop),
        # so bail rather than update/scroll a detached widget.
        if not reply_widget.is_mounted:
            _finish()
            return
        shown["count"] += 1
        body = " ".join(words[: shown["count"]])
        done = shown["count"] >= len(words)
        text = transcript_mod.styled_line(
            header + "\n", Style(color=accent, bold=True), body + ("" if done else " ▋")
        )
        reply_widget.update(text)
        transcript.scroll_end(animate=False)
        if done:
            _finish()

    # Its own tracked timer, not a shared single slot: two personas' replies
    # (or two queued same-persona replies processed back-to-back) can now
    # genuinely stream at once post-lock — the lock only serializes the
    # engine call, not this word-by-word reveal (docs/decisions/008).
    timer = app.set_interval(0.05, tick)
    app.active_reply_timers.add(timer)
