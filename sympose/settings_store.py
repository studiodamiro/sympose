"""
App-wide settings storage — one JSON file for backend-written knobs that
need to survive a restart (today: which vault is active; per ADR 003, a
future compaction default / Slack allowlist land here too rather than
each growing its own storage mechanism). Distinct from `profiles/*.yaml`,
which is hand-authored persona config, and from `.env`, which is
deployment config: this file is only ever written by the backend itself
in response to a UI action.
"""

import json
import logging
import os
from typing import Any

from sympose.atomic_write import write_atomic_text

log = logging.getLogger(__name__)


def settings_path() -> str:
    return os.getenv("SYMPOSE_SETTINGS_PATH") or os.path.join(
        os.getcwd(), "settings.json"
    )


def _load() -> dict[str, Any]:
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):  # ValueError: not JSON, or not valid UTF-8
        return {}


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def flag(key: str, default: bool = True) -> bool:
    """A true/false knob: only an actual boolean counts, anything else (a
    hand-edited `"false"`, `0`, `null`) leaves it at `default`, so a
    malformed value never silently flips a setting."""
    value = get(key, default)
    return value if isinstance(value, bool) else default


def is_name(value: Any) -> bool:
    """Whether a setting holds a usable name: a string with something in it."""
    return isinstance(value, str) and bool(value.strip())


def text(key: str, default: str) -> str:
    """A name-like knob: only a non-blank string counts, anything else (a
    hand-edited `null`, `""`, a number or a list) leaves it at `default`, so
    a malformed value never reaches code that expects a string."""
    value = get(key, default)
    return value if is_name(value) else default


def set(key: str, value: Any) -> bool:
    """Merges `key: value` into the settings file and writes it back
    whole — the file is small (a handful of app-wide knobs), so a
    read-modify-write on every call is simpler than an in-memory cache
    that a second backend process could silently drift from."""
    data = _load()
    data[key] = value
    return _write(data)


def remove(key: str) -> bool:
    """Drops `key` so its default applies again. A missing key, or a file
    that cannot be read, is left exactly as it is (nothing to drop, and a
    damaged file is never overwritten with what is left of it)."""
    data = _load()
    if key not in data:
        return True
    del data[key]
    return _write(data)


def _write(data: dict[str, Any]) -> bool:
    text = json.dumps(data, indent=2)  # first: a value that is not JSON raises here, with the file untouched
    try:
        os.makedirs(os.path.dirname(settings_path()) or ".", exist_ok=True)
        write_atomic_text(settings_path(), text)  # whole or not at all: this file is all the configuration
        return True
    except OSError as e:
        log.warning("Failed to write %s: %s", settings_path(), e)
        return False
