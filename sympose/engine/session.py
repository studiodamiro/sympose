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
from datetime import datetime, timezone
from typing import Any

from sympose.engine.session_paths import (
    new_session_id,
    recaps_dir,
    session_ids,
    session_path,
    sessions_dir,
)

# The path helpers live in `session_paths`; callers keep reaching them here.
__all__ = [
    "append_turn",
    "history_as_messages",
    "load_session",
    "new_session_id",
    "recaps_dir",
    "session_ids",
    "session_path",
    "sessions_dir",
]

log = logging.getLogger(__name__)

_TITLE_WORDS = 6


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
    sent: dict[str, Any] | None = None,
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
    lack the keys, and nothing reading a session depends on them. `sent`
    (docs/decisions/025) is what reached the model besides the messages: kept on
    the record for diagnosis and never read back into a prompt."""
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
            **({"sent": sent} if sent is not None else {}),
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
