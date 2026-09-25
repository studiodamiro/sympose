"""Where a persona's files live and how its soul is read (docs/decisions/011, 012):
`<profiles_dir>/<handle>/` holds `persona.yaml`, `soul.md`, and later memory,
expertise and sessions. Split out of `profile.py`, which keeps the roster,
the default persona and the fail-closed lookup (docs/decisions/009)."""

import logging
import os

from sympose.security import is_safe_path

log = logging.getLogger(__name__)

PERSONA_FILENAME = "persona.yaml"
SOUL_FILENAME = "soul.md"


def profiles_dir() -> str:
    return os.getenv("SYMPOSE_PROFILES_DIR") or os.path.join(os.getcwd(), "profiles")


def persona_dir(handle: str) -> str:
    """`<profiles_dir>/<handle>/` — everything belonging to one persona
    (config, and later soul/memory/expertise/sessions) lives here
    (docs/decisions/011). Raises `ValueError` unless `handle` is a single
    plain path component: `is_safe_path` alone only proves a path stays
    inside `profiles/`, which `.` (the directory itself) and `a/b` (a
    nested path) both do without naming one persona's own directory."""
    handle = handle.lower()
    if handle in ("", ".", "..") or os.path.basename(handle) != handle:
        raise ValueError(f"Not a valid persona handle: {handle!r}")
    return os.path.join(profiles_dir(), handle)


def load_soul(handle: str) -> str | None:
    """The persona's `soul.md` text (docs/decisions/012), or `None` when it
    has none — missing, empty, unsafe path, or unreadable — so the caller
    can fall back to a generic soul. Read on demand rather than inside
    `get_profile`, which runs on every vault route that has no use for it;
    an edit to the file takes effect on the next call."""
    try:
        path = os.path.join(persona_dir(handle), SOUL_FILENAME)
    except ValueError:
        return None
    if not is_safe_path(path, profiles_dir()):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as e:
        log.warning("Couldn't read %s, using the default soul: %s", path, e)
        return None
