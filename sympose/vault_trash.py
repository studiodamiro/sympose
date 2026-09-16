"""
`<vault>/.trash` recovery surface (ADR-085).

`VaultManager.delete_note` (vault.py, ADR-084) moves a note to
`<vault>/.trash/<original relpath>` instead of unlinking it. This module is
the read / restore / purge half of that contract: list what is recoverable,
move one note back to where it came from, or unlink it for good.

Stdlib only. Every function sandbox-checks both ends against the caller's
allowed vault folders and never raises across the API boundary — a bad path
comes back as a typed sentinel, not a 500. `.trash` ships in the default
`vault.ignore_folders`, so trashed notes never reach the search index, the
manifest, or a persona's grounding while they sit here.
"""

import json
import logging
import os
import threading
from typing import Any

from sympose.compactor import get_or_create_lock
from sympose.config import is_safe_path

log = logging.getLogger(__name__)

TRASH_DIRNAME = ".trash"

# Sentinels — mapped onto VaultManager.NOTE_* by the thin wrappers in vault.py
# so the server sees one consistent status vocabulary.
NOT_IN_TRASH = "__trash_not_found__"
TARGET_EXISTS = "__trash_target_exists__"
DENIED = "__trash_denied__"

# `delete_note` appends `-YYYYMMDDHHMMSS` before `.md` when a same-named note
# is already in the trash. D4: that suffix used to be *inferred* by stripping
# a trailing `-\d{14}` via regex, which false-positived on a legitimately
# timestamp-named file (e.g. a real `Meeting-20240315120000.md`), silently
# computing the wrong restore target. `INDEX_FILENAME` instead *records* the
# original path explicitly at delete time - a `{trash_rel: original_rel}`
# sidecar, consulted only for the (rare) trash_rel that actually needed a
# clash suffix; every other trashed file's trash_rel already *is* its
# original_rel, so the common case needs no lookup at all.
INDEX_FILENAME = ".trash-index.json"

_index_locks_guard = threading.Lock()
_index_locks: dict[str, threading.Lock] = {}


def _index_path(troot: str) -> str:
    return os.path.join(troot, INDEX_FILENAME)


def _load_index(troot: str) -> dict[str, str]:
    try:
        with open(_index_path(troot), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_index(troot: str, index: dict[str, str]) -> None:
    path = _index_path(troot)
    lock = get_or_create_lock(_index_locks, _index_locks_guard, path)
    with lock:
        tmp = f"{path}.{os.getpid()}.tmp"
        try:
            os.makedirs(troot, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as e:
            log.debug("Failed to persist trash index %s: %s", path, e)


def record_clash(troot: str, trash_rel: str, original_rel: str) -> None:
    """Called by `delete_note` (vault_write.py) only when a same-named
    clash actually forced a timestamp suffix onto `trash_rel` - the
    non-clash common case needs no index entry, since `trash_rel` already
    equals `original_rel` there."""
    index = _load_index(troot)
    index[trash_rel] = original_rel
    _save_index(troot, index)


def _original_relpath(troot: str, trash_rel: str) -> str:
    """Vault-relative path the note occupied before deletion. Looked up from
    the clash index when `trash_rel` needed a disambiguating suffix;
    otherwise `trash_rel` already *is* the original path."""
    return _load_index(troot).get(trash_rel, trash_rel)


def _forget_clash(troot: str, trash_rel: str) -> None:
    """Drops `trash_rel`'s index entry once it's restored or purged, so the
    sidecar doesn't accumulate stale rows forever."""
    index = _load_index(troot)
    if trash_rel in index:
        del index[trash_rel]
        _save_index(troot, index)


def _prune_empty_dirs(root: str, start: str) -> None:
    """Walk up from `start`, removing now-empty directories, stopping at `root`
    (exclusive) or the first non-empty parent. Best-effort."""
    cur = start
    try:
        root_real = os.path.realpath(root)
        while os.path.realpath(cur) != root_real and is_safe_path(cur, root):
            if os.listdir(cur):
                break
            os.rmdir(cur)
            cur = os.path.dirname(cur)
    except OSError:
        pass


def list_trashed(mv: str, allowed_dirs: list[str]) -> list[dict[str, Any]]:
    """Recoverable notes under `<mv>/.trash`, newest deletion first. Each row:
    `{trash_path, original_path, deleted_at (mtime epoch), size}`. Scoped to the
    persona — an entry whose original location sits outside `allowed_dirs` is
    omitted."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    if not os.path.isdir(troot):
        return []
    rows: list[dict[str, Any]] = []
    for cur, dirs, files in os.walk(troot):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(cur, fn)
            if not is_safe_path(fp, troot):
                continue
            trash_rel = os.path.relpath(fp, troot).replace(os.sep, "/")
            orig_rel = _original_relpath(troot, trash_rel)
            orig_abs = os.path.join(mv, orig_rel)
            if not any(is_safe_path(orig_abs, a) for a in allowed_dirs):
                continue
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rows.append(
                {
                    "trash_path": trash_rel,
                    "original_path": orig_rel,
                    "deleted_at": st.st_mtime,
                    "size": st.st_size,
                }
            )
    rows.sort(key=lambda r: r["deleted_at"], reverse=True)
    return rows


def _resolve_in_trash(mv: str, trash_rel: str) -> Any:
    """Absolute path of `trash_rel` under `<mv>/.trash`, or a `DENIED` /
    `NOT_IN_TRASH` sentinel."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = os.path.normpath(os.path.join(troot, (trash_rel or "").lstrip("/\\")))
    if not is_safe_path(src, troot):
        return DENIED
    if not os.path.isfile(src):
        return NOT_IN_TRASH
    return src


def restore(mv: str, allowed_dirs: list[str], trash_rel: str) -> str:
    """Move a trashed note back to its original vault-relative path. Returns that
    path on success, or `NOT_IN_TRASH` / `TARGET_EXISTS` (something occupies the
    original spot now) / `DENIED` / `"Error: …"`."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (DENIED, NOT_IN_TRASH):
        return src

    trash_rel_actual = os.path.relpath(src, troot).replace(os.sep, "/")
    orig_rel = _original_relpath(troot, trash_rel_actual)
    dst = os.path.normpath(os.path.join(mv, orig_rel))
    if not any(is_safe_path(dst, a) for a in allowed_dirs):
        return DENIED
    if os.path.exists(dst):
        return TARGET_EXISTS
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
    except OSError as e:
        return f"Error: Failed to restore note: {e}"
    _forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    return os.path.relpath(dst, mv).replace(os.sep, "/")


def purge(mv: str, allowed_dirs: list[str], trash_rel: str) -> str:
    """Permanently unlink one trashed note. Returns `""` on success, or
    `NOT_IN_TRASH` / `DENIED` / `"Error: …"`. Scoped: an entry whose original
    location is outside `allowed_dirs` cannot be purged through this persona."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (DENIED, NOT_IN_TRASH):
        return src

    trash_rel_actual = os.path.relpath(src, troot).replace(os.sep, "/")
    orig_rel = _original_relpath(troot, trash_rel_actual)
    if not any(is_safe_path(os.path.join(mv, orig_rel), a) for a in allowed_dirs):
        return DENIED
    try:
        os.remove(src)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    _forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    return ""


def purge_all(mv: str, allowed_dirs: list[str]) -> int:
    """Empty the trash of every in-scope note. Returns the count removed."""
    removed = 0
    for row in list_trashed(mv, allowed_dirs):
        if purge(mv, allowed_dirs, row["trash_path"]) == "":
            removed += 1
    return removed
