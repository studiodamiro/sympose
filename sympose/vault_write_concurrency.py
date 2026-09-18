"""
Optimistic-Concurrency Guard for Vault Writes (ADR-129) — not distributed
locking.

Today, two writers racing on the same vault file — two Sympose processes,
or the same process from two threads — silently last-write-wins: nothing
checks whether the file changed between when a caller last read it and
when it writes back. This lets a caller that knows the mtime it last read
detect that the file moved under it before overwriting, without inventing
any cross-process or cross-machine coordination (a real distributed lock
is explicitly out of scope — whatever sync layer, if any, moves a vault
between machines is responsible for reconciling that before Sympose ever
sees it).

Opt-in per call via `expected_mtime=None` (the default, meaning "no
precondition — behave exactly as before"). Gated project-wide by
`vault.multi_writer_safety` (default `False`) so a single-writer user
pays zero cost.
"""

import os

# Mapped onto VaultManager.NOTE_* the same way NOTE_NOT_FOUND/NOTE_DENIED
# already are (vault_write.py), so the server sees one consistent status
# vocabulary regardless of which module a result actually came from.
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
