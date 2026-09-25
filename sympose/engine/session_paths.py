"""Where a persona's session logs and recaps live (docs/decisions/006, 011, 023):
the directory layout, the whole-vault fallback mode, session ids, and the checks
that keep a handle or a session id inside its own place."""

import os
import uuid
from datetime import datetime, timezone

from sympose.persona_files import persona_dir, profiles_dir
from sympose.security import is_safe_path


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


def recaps_dir(handle: str) -> str:
    """Where `handle`'s recaps of earlier sessions live (docs/decisions/023), beside
    its sessions: `profiles/<handle>/recaps/`, or `./recaps/<handle>/` in the
    whole-vault fallback mode. Same path checks as `sessions_dir`."""
    persona = persona_dir(handle)
    if _fallback_mode():
        return os.path.join(os.getcwd(), "recaps", handle.lower())
    return os.path.join(persona, "recaps")


def session_ids(handle: str) -> list[str]:
    """The ids of `handle`'s saved sessions, newest first (an id starts with the
    time the session began, so the names sort by age)."""
    try:
        names = os.listdir(sessions_dir(handle))
    except OSError:
        return []
    return sorted((n.removesuffix(".jsonl") for n in names if n.endswith(".jsonl")), reverse=True)


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
