"""What a session file's records are made of (docs/decisions/006): the title, the parts a damaged file
can lack, and the check for a file that cannot be read. Split out of `session` to keep it small."""

import os
from datetime import datetime, timezone
from typing import Any

_TITLE_WORDS = 6


def make_title(user_message: str) -> str:
    words = user_message.split()
    title = " ".join(words[:_TITLE_WORDS])
    return title + "..." if len(words) > _TITLE_WORDS else title


def has_its_text(turn: dict[str, Any]) -> bool:
    return isinstance(turn.get("user"), str) and isinstance(turn.get("assistant"), str)


def meta_from_turns(handle: str, session_id: str, turns: list[dict[str, Any]], path: str) -> dict[str, Any]:
    """The meta line of a file that lost it, from the turns that are still there."""
    modified = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
    return {
        "type": "meta",
        "session_id": session_id,
        "handle": handle.lower(),
        "title": make_title(turns[0]["user"]),
        "created_at": turns[0].get("timestamp") or modified,
        "updated_at": turns[-1].get("timestamp") or modified,
        "turns_count": len(turns),
    }


def unreadable(path: str) -> bool:
    """A file that exists but cannot be opened for reading (permissions, a fault)."""
    try:
        with open(path, "rb"):
            return False
    except FileNotFoundError:
        return False
    except OSError:
        return True
