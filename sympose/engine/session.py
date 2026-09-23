"""Per-conversation session log — one JSONL file per session
(docs/decisions/006): a meta line followed by one line per turn. Nothing is
written to disk until a session's first turn, so a session that's opened but
never used leaves no file behind — pruning-by-omission, no separate sweep
needed. Same read-modify-write-whole-file posture as `settings_store.set`,
not lock-hardened; safe because each persona's own file only ever has one
turn in flight at a time (`sympose/cli/turns.py`'s per-handle locking,
docs/decisions/008) — a global "one turn process-wide" guarantee was never
actually needed, since two different personas' files can't collide anyway."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sympose.profile import persona_dir, profiles_dir
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

_TITLE_WORDS = 6


def _fallback_mode() -> bool:
    """No `profiles/` directory at all — the whole-vault fallback mode.
    Sessions then go in `./sessions` instead of under `profiles/`: writing
    there would create that directory, and creating it would flip the
    whole system out of fallback mode as a side effect of a chat
    (docs/decisions/011)."""
    return not os.path.isdir(profiles_dir())


def _sessions_root() -> str:
    """The directory every persona's sessions must stay inside."""
    return os.path.join(os.getcwd(), "sessions") if _fallback_mode() else profiles_dir()


def sessions_dir(handle: str) -> str:
    """Where `handle`'s sessions live: `profiles/<handle>/sessions/`, or
    `./sessions/<handle>/` in fallback mode. `persona_dir` runs first in
    both modes so a handle that isn't one plain path component (`.`, `a/b`)
    is rejected the same way everywhere."""
    persona = persona_dir(handle)
    if _fallback_mode():
        return os.path.join(_sessions_root(), handle.lower())
    return os.path.join(persona, "sessions")


def session_path(handle: str, session_id: str) -> str:
    directory = sessions_dir(handle)
    path = os.path.join(directory, f"{session_id}.jsonl")
    # Two checks, not one: the handle must not escape the root (a `../x`
    # handle would otherwise make `directory` itself the trusted base), and
    # the session id must not escape its own persona's directory into a
    # sibling persona's files.
    if not is_safe_path(directory, _sessions_root()) or not is_safe_path(path, directory):
        raise ValueError(f"Unsafe session path for handle={handle!r} session_id={session_id!r}")
    return path


def new_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _make_title(user_message: str) -> str:
    words = user_message.split()
    title = " ".join(words[:_TITLE_WORDS])
    return title + "..." if len(words) > _TITLE_WORDS else title


def load_session(handle: str, session_id: str) -> dict[str, Any] | None:
    """`{"meta": {...}, "turns": [...]}`, or `None` when the session has no
    file yet (never used) or the file is missing/corrupt."""
    path = session_path(handle, session_id)
    if not os.path.exists(path):
        return None
    meta: dict[str, Any] | None = None
    turns: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        log.warning("Failed to read session %s: %s", path, e)
        return None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            # One truncated/malformed line (e.g. a crash mid-write) must
            # not discard every other, valid line in the file — skip just
            # this one rather than failing the whole read.
            log.warning("Skipping malformed line in session %s: %s", path, e)
            continue
        if not isinstance(obj, dict):
            continue  # valid JSON but not an object — same treatment
        if obj.get("type") == "meta":
            meta = obj
        elif obj.get("type") == "turn":
            turns.append(obj)
    return {"meta": meta, "turns": turns} if meta is not None else None


def history_as_messages(session: dict[str, Any] | None, max_turns: int = 20) -> list[dict[str, str]]:
    if not session or max_turns <= 0:
        return []
    messages: list[dict[str, str]] = []
    for turn in session["turns"][-max_turns:]:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})
    return messages


def append_turn(
    handle: str,
    session_id: str,
    user_message: str,
    reply: str,
    existing: dict[str, Any] | None = None,
    ttft_ms: int | None = None,
    model: str | None = None,
) -> None:
    """`existing` lets a caller that's already loaded the session (e.g.
    `turn.run_turn`, which loads it to build history) pass it straight
    through instead of this function re-reading and re-parsing an existing
    session file a second time in the same turn. Left unspecified, it's
    loaded here instead — cheap for a genuinely new session (a single
    `os.path.exists` check, not a real parse), so a plain
    `append_turn(handle, sid, msg, reply)` call still works standalone.

    `ttft_ms` and `model` (docs/decisions/013) are stored on the turn record
    as-is, `null` when unknown; records written before they existed simply
    lack the keys, and nothing reading a session depends on them."""
    session = existing if existing is not None else load_session(handle, session_id)
    now = datetime.now(timezone.utc).isoformat()

    if session is None:
        meta: dict[str, Any] = {
            "type": "meta",
            "session_id": session_id,
            "handle": handle.lower(),
            "title": _make_title(user_message),
            "created_at": now,
            "updated_at": now,
            "turns_count": 0,
        }
        turns: list[dict[str, Any]] = []
    else:
        meta = session["meta"]
        turns = session["turns"]

    turns.append(
        {
            "type": "turn",
            "timestamp": now,
            "user": user_message,
            "assistant": reply,
            "ttft_ms": ttft_ms,
            "model": model,
        }
    )
    meta["updated_at"] = now
    meta["turns_count"] = len(turns)

    path = session_path(handle, session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")
            for turn in turns:
                f.write(json.dumps(turn) + "\n")
    except OSError as e:
        log.warning("Failed to write session %s: %s", path, e)
