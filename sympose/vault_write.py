"""
Vault note writes: `overwrite_note` (the web app editor saving an
*existing* note back to disk verbatim), plus the shared primitives
(`get_file_lock`, `write_atomic_text`) that `vault_write_create.py`,
`vault_write_delete.py`, and `vault_write_rename.py` build on.
"""

import os
import threading
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator

from sympose import vault_paths
from sympose.vault_write_concurrency import NOTE_CONFLICT, mtime_matches
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def get_file_lock(path: str) -> threading.Lock:
    """One lock per absolute file path, so two writers racing on the same
    note serialize instead of interleaving their writes."""
    with _locks_guard:
        lock = _locks.get(path)
        if lock is None:
            lock = _locks[path] = threading.Lock()
        return lock


@contextmanager
def get_file_locks(*paths: str) -> Iterator[None]:
    """Acquires `get_file_lock` for each of `paths`, always in sorted order —
    an operation that needs two paths locked at once (a rename's source and
    destination, a restore's trash source and original destination) must
    always acquire them in the same order as any other operation racing it,
    or two such operations can deadlock each acquiring one lock and waiting
    on the other."""
    with ExitStack() as stack:
        for p in sorted(set(paths)):
            stack.enter_context(get_file_lock(p))
        yield


def write_atomic_text(path: str, content: str) -> None:
    """Writes `content` to `path` via a tmp file + `os.replace` — the rename
    is atomic on the same filesystem, so a crash mid-write can't leave
    `path` truncated."""
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def overwrite_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    expected_mtime: float | None = None,
) -> str:
    """Replace an *existing* vault note's file with `content`, verbatim (the
    editor already owns the whole document, frontmatter included). Resolves
    the same file a read would return, so a web app save lands back on the
    note it was opened from. Overwrite only — a path with no existing file
    returns `NOTE_NOT_FOUND` rather than creating one; a path outside the
    persona's sandbox returns `NOTE_DENIED`; a caller-supplied
    `expected_mtime` that no longer matches the file on disk returns
    `NOTE_CONFLICT` instead of clobbering a concurrent write."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope

    target_file = resolve_existing_note(profile, note_name)
    if target_file is None:
        return NOTE_NOT_FOUND
    if not vault_paths.is_within_any(target_file, allowed_dirs):
        return NOTE_DENIED
    with get_file_lock(target_file):
        if not mtime_matches(target_file, expected_mtime):
            return NOTE_CONFLICT

        rel_display = os.path.relpath(target_file, mv)
        try:
            write_atomic_text(target_file, content.rstrip("\n") + "\n")
            return f"Saved note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"
