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
    except (OSError, json.JSONDecodeError):
        return {}


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set(key: str, value: Any) -> bool:
    """Merges `key: value` into the settings file and writes it back
    whole — the file is small (a handful of app-wide knobs), so a
    read-modify-write on every call is simpler than an in-memory cache
    that a second backend process could silently drift from."""
    data = _load()
    data[key] = value
    try:
        os.makedirs(os.path.dirname(settings_path()) or ".", exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as e:
        log.warning("Failed to write %s: %s", settings_path(), e)
        return False
