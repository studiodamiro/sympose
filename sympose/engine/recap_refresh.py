"""Writing the recaps (docs/decisions/023): which sessions get one, what the model is
asked, and the background run at launch. Reading them back is `recap`."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sympose import profile as profile_mod
from sympose.engine import budget, prompt, recap, session
from sympose.engine import model as model_mod

log = logging.getLogger(__name__)

# Of the newest sessions at most `_SCAN` are looked at, and of those the newest
# `_CONSIDERED` that are worth a recap: a few throwaway sessions must not starve a real one.
_SCAN = 10
_CONSIDERED = 3
_MIN_TURNS = 2
# A very long session is recapped from its last turns, so the request stays small.
_MAX_TURNS = 40
# A session touched this recently may still be running in another window.
_QUIET = timedelta(minutes=30)
_MAX_RECAP_TOKENS = 200
_MAX_USER_CHARS = 1000

# A model that spent its whole small reply limit thinking cannot write a recap
# (as with the follow-up rewrite, ADR 017): not asked again until the process restarts.
_CANNOT_RECAP: set[str] = set()


def _transcript(turns: list[dict[str, Any]]) -> str:
    """The user's own messages only: the persona's replies include what it got wrong or
    made up, and a recap that records them turns that into something "the user said"."""
    return "\n".join(f"User: {turn['user'][:_MAX_USER_CHARS]}" for turn in turns)


def _request(turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    body = f"Conversation:\n{_transcript(turns)}\n\nRecap:"
    return [{"role": "system", "content": prompt.RECAP_INSTRUCTIONS}, {"role": "user", "content": body}]


def _fitting(turns: list[dict[str, Any]], model: str, limits: budget.Budget | None) -> list[dict[str, Any]]:
    """The newest turns whose recap request fits the model's window."""
    kept = list(turns)
    while kept and limits is not None and budget.count_tokens(_request(kept), model) > limits.prompt_tokens:
        del kept[0]
    return kept


def _clean(text: str) -> str | None:
    """The recap as it is to be kept: `""` when the model said there is nothing to
    carry over, `None` when it wrote nothing."""
    text = " ".join(text.split())
    if not text:
        return None
    if text.rstrip(".! ").upper() == prompt.NO_RECAP:
        return ""
    return text


def _write_one(
    handle: str, session_id: str, session_turns: list[dict[str, Any]], model: str, limits: budget.Budget | None
) -> bool:
    """Ask the model for one recap and keep it; `False` when the model cannot
    be used right now, so the caller stops instead of trying every session."""
    turns = _fitting(session_turns[-_MAX_TURNS:], model, limits)
    if not turns:
        return True  # nothing of it fits the window: leave it, not a model failure
    try:
        reply = model_mod.call_model(
            _request(turns),
            model=model,
            num_ctx=limits.num_ctx if limits else None,
            max_tokens=_MAX_RECAP_TOKENS,
        )
    except model_mod.ReplyLimitError as e:
        log.warning("'%s' cannot write a recap in its reply limit; not asking again: %s", model, e)
        _CANNOT_RECAP.add(model)
        return False
    except model_mod.EngineModelError as e:
        log.warning("Recap of session %s failed: %s", session_id, e)
        return False
    text = _clean(reply.text)
    if reply.truncated and text:  # cut mid-sentence: stop at the last whole one
        cut = max(text.rfind(mark) for mark in ".!?")
        text = text[: cut + 1] if cut > 0 else None
    if text is None:
        return False  # nothing usable: stop, so a model that keeps doing this costs one call per launch
    try:
        recap.write(handle, session_id, len(session_turns), text)
    except OSError as e:
        log.warning("Could not save the recap of session %s: %s", session_id, e)
        return False
    return True


def refresh(handle: str, now: datetime | None = None) -> None:
    """Write the recaps that are missing (or out of date) for `handle`'s newest
    sessions. Never raises for a model or file problem: the session simply has no
    recap yet and is looked at again the next time."""
    persona = profile_mod.resolve_profile(handle)
    if persona is None or not recap.enabled():
        return
    model = model_mod.resolve_model(persona.get("model"))
    if model in _CANNOT_RECAP:
        return
    limits = budget.budget_for(model)
    now = now or datetime.now(timezone.utc)
    worth_a_recap = 0
    for session_id in session.session_ids(handle)[:_SCAN]:
        if worth_a_recap == _CONSIDERED:
            break
        loaded = session.load_session(handle, session_id)
        if not loaded or len(loaded["turns"]) < _MIN_TURNS:
            continue
        try:
            updated = datetime.fromisoformat(loaded["meta"]["updated_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if updated.tzinfo is None:  # the logs write UTC; a hand-edited stamp may lack the zone
            updated = updated.replace(tzinfo=timezone.utc)
        if now - updated < _QUIET:
            continue
        worth_a_recap += 1
        existing = recap.load(handle, session_id)
        if existing is not None and (existing[0] is None or existing[0] >= len(loaded["turns"])):
            continue  # the user's own file, or a recap that already covers the session
        if not _write_one(handle, session_id, loaded["turns"], model, limits):
            return


# One run per persona at a time; the event is set when it finishes.
_RUNNING: dict[str, threading.Event] = {}
_RUNNING_LOCK = threading.Lock()
# How long a turn waits for a refresh that is still running. The refresh is one small
# model call on the model the turn needs anyway, so the turn would queue behind it on
# a single GPU regardless (measured, ADR 023); a stuck call must not hold a turn for long.
_WAIT_SECONDS = 20.0


def refresh_in_background(handle: str) -> bool:
    """Start `refresh` on a daemon thread and return at once, so the user can type
    their first message meanwhile and quitting never waits on a model call. `False`
    when one is already running for `handle` (a persona switched to twice)."""
    with _RUNNING_LOCK:
        if handle in _RUNNING:
            return False
        done = _RUNNING[handle] = threading.Event()

    def work() -> None:
        try:
            refresh(handle)
        except Exception as e:  # a background thread must not print a traceback into the terminal
            log.warning("Recap refresh for %s failed: %s", handle, e)
        finally:
            with _RUNNING_LOCK:
                del _RUNNING[handle]
            done.set()

    threading.Thread(target=work, name=f"recaps-{handle}", daemon=True).start()
    return True


def wait_for_refresh(handle: str, timeout: float = _WAIT_SECONDS) -> bool:
    """Give a refresh that is running for `handle` up to `timeout` seconds to finish,
    so a message sent straight after launch still gets the recap it is about. `True`
    when none is running or it finished, `False` when it is still going."""
    with _RUNNING_LOCK:
        done = _RUNNING.get(handle)
    return True if done is None else done.wait(timeout)
