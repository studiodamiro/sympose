"""
Optimistic-Concurrency Guard for Vault Writes — not distributed locking.

Two writers racing on the same vault file — two Sympose processes, or the
same process from two threads — would otherwise silently last-write-win:
nothing checks whether the file changed between when a caller last read it
and when it writes back. This lets a caller that knows the mtime it last
read detect that the file moved under it before overwriting, without
inventing any cross-process or cross-machine coordination.

Opt-in per call via `expected_mtime=None` (the default, meaning "no
precondition — behave exactly as before").
"""

import os

NOTE_CONFLICT = "__note_conflict__"


def current_mtime(path: str) -> float | None:
    """The file's current mtime, or None if it doesn't exist."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def mtime_matches(path: str, expected: float | None) -> bool:
    """True when no precondition was given (`expected is None` — the
    caller isn't opting into the guard for this write), or when the file's
    current mtime matches what the caller last read. A file that no longer
    exists (`current_mtime` returns `None`) only "matches" an `expected`
    of `None`, so a caller that thought the file existed correctly sees a
    conflict rather than silently creating a new one."""
    if expected is None:
        return True
    return current_mtime(path) == expected
