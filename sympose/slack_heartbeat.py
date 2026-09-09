"""
Slack daemon liveness heartbeat (ADR-082).

The `sympose --slack` daemon and the `sympose --dashboard` server are separate
processes with no IPC. To let the dashboard show whether Slack is up, the daemon
writes a small JSON heartbeat into the workspace on a timer; the dashboard reads
its age. A stale file (daemon crashed or was killed) ages into "offline" on its
own — no PID tracking, no cleanup contract to get wrong.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

HEARTBEAT_FILENAME = ".slack_heartbeat.json"

# Written every `WRITE_INTERVAL`s; older than `STALE_AFTER`s means the daemon has
# missed a beat (hung, or stopped between writes); older than `OFFLINE_AFTER`s
# means it is gone. Kept as a 1 : ~3 : ~8 ratio so one skipped write is not
# mistaken for a dead daemon.
WRITE_INTERVAL = 15
STALE_AFTER = 45
OFFLINE_AFTER = 120


def heartbeat_path(workspace_dir: str) -> str:
    return os.path.join(workspace_dir, HEARTBEAT_FILENAME)


def write_heartbeat(workspace_dir: str, personas: List[str]) -> None:
    """Stamp the heartbeat file with the current time, this pid, and the live
    persona handles. Atomic (write-temp-then-rename) so a concurrent read never
    sees a half-written file. Best-effort — a write failure is not worth
    crashing the daemon over."""
    payload = {"ts": time.time(), "pid": os.getpid(), "personas": sorted(personas)}
    path = heartbeat_path(workspace_dir)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def clear_heartbeat(workspace_dir: str) -> None:
    """Remove the heartbeat on a clean daemon exit so the dashboard flips to
    "offline" immediately rather than after the staleness timeout."""
    try:
        os.unlink(heartbeat_path(workspace_dir))
    except OSError:
        pass


def read_status(workspace_dir: str, *, now: Optional[float] = None) -> Dict[str, Any]:
    """Project the heartbeat file into `{state, last_seen, age_seconds,
    personas, pid}` for `GET /api/slack/status`.

    - no file, unreadable, or older than `OFFLINE_AFTER` -> ``"offline"``
    - older than `STALE_AFTER` -> ``"stale"``
    - otherwise -> ``"connected"``
    """
    now = time.time() if now is None else now
    offline = {
        "state": "offline",
        "last_seen": None,
        "age_seconds": None,
        "personas": [],
        "pid": None,
    }
    try:
        with open(heartbeat_path(workspace_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = float(data["ts"])
    except (OSError, ValueError, KeyError, TypeError):
        return offline

    age = max(0.0, now - ts)
    if age > OFFLINE_AFTER:
        state = "offline"
    elif age > STALE_AFTER:
        state = "stale"
    else:
        state = "connected"

    result = {
        "state": state,
        "last_seen": ts,
        "age_seconds": round(age, 1),
        "personas": data.get("personas") or [],
        "pid": data.get("pid"),
    }
    if state == "offline":
        # Keep `last_seen` for the UI's "last seen 5m ago", but nothing else.
        result["personas"] = []
    return result
