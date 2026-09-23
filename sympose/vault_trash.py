"""
`<vault>/.trash` recovery surface.

`vault_write_delete.delete_note` moves a note to `<vault>/.trash/<original
relpath>` instead of unlinking it. This module is the read / restore / purge
half of that contract: list what is recoverable, move one note back to
where it came from, or unlink it for good. The clash-index sidecar that
tracks a timestamp-suffixed trash name's real original path lives in
`vault_trash_index.py`.

Every function sandbox-checks both ends against the caller's allowed vault
folders and never raises across the API boundary — a bad path comes back as
one of `vault_write_status`'s shared sentinels, not a 500.
"""

import os
from typing import Any

from sympose.security import is_safe_path
from sympose.vault_paths import is_within_any
from sympose.vault_trash_index import forget_clash, load_index, original_relpath
from sympose.vault_write import get_file_lock, get_file_locks
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND

TRASH_DIRNAME = ".trash"


def _prune_empty_dirs(root: str, start: str) -> None:
    """Walk up from `start`, removing now-empty directories, stopping at
    `root` (exclusive) or the first non-empty parent. Best-effort."""
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
    `{trash_path, original_path, deleted_at (mtime epoch), size}`. Scoped to
    the persona — an entry whose original location sits outside
    `allowed_dirs` is omitted."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    if not os.path.isdir(troot):
        return []
    # Loaded once for the whole listing — `original_relpath` alone would
    # re-read the index file from disk once per trashed item.
    index = load_index(troot)
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
            orig_rel = index.get(trash_rel, trash_rel)
            orig_abs = os.path.join(mv, orig_rel)
            if not is_within_any(orig_abs, allowed_dirs):
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


def _resolve_in_trash(mv: str, trash_rel: str) -> str:
    """Absolute path of `trash_rel` under `<mv>/.trash`, or a `NOTE_DENIED` /
    `NOTE_NOT_FOUND` sentinel."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = os.path.normpath(os.path.join(troot, (trash_rel or "").lstrip("/\\")))
    if not is_safe_path(src, troot):
        return NOTE_DENIED
    if not os.path.isfile(src):
        return NOTE_NOT_FOUND
    return src


def _resolve_trash_entry(
    mv: str, trash_rel: str
) -> tuple[str, str, str, str] | str:
    """Resolves a trash-relative path to (`src`, `troot`, `trash_rel_actual`,
    `orig_rel`) — the trashed file's absolute path, the trash root, its
    actual trash-relative path, and its recorded original vault-relative
    path — or a `NOTE_DENIED`/`NOTE_NOT_FOUND` sentinel."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (NOTE_DENIED, NOTE_NOT_FOUND):
        return src
    trash_rel_actual = os.path.relpath(src, troot).replace(os.sep, "/")
    orig_rel = original_relpath(troot, trash_rel_actual)
    return src, troot, trash_rel_actual, orig_rel


def restore(mv: str, allowed_dirs: list[str], trash_rel: str) -> str:
    """Move a trashed note back to its original vault-relative path. Returns
    that path on success, or `NOTE_NOT_FOUND` / `NOTE_EXISTS` (something
    occupies the original spot now) / `NOTE_DENIED` / `"Error: …"`."""
    entry = _resolve_trash_entry(mv, trash_rel)
    if isinstance(entry, str):
        return entry
    src, troot, trash_rel_actual, orig_rel = entry
    dst = os.path.normpath(os.path.join(mv, orig_rel))
    if not is_within_any(dst, allowed_dirs):
        return NOTE_DENIED
    # Locks both ends: `src` against a concurrent restore/purge of the same
    # trash entry, `dst` against a concurrent create/restore landing on the
    # same original path — the same double-lock shape `overwrite_note` uses.
    with get_file_locks(src, dst):
        if os.path.exists(dst):
            return NOTE_EXISTS
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            return f"Error: Failed to restore note: {e}"
    forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    return os.path.relpath(dst, mv).replace(os.sep, "/")


def purge(mv: str, allowed_dirs: list[str], trash_rel: str) -> str:
    """Permanently unlink one trashed note. Returns `""` on success, or
    `NOTE_NOT_FOUND` / `NOTE_DENIED` / `"Error: …"`. Scoped: an entry whose
    original location is outside `allowed_dirs` cannot be purged through
    this persona."""
    entry = _resolve_trash_entry(mv, trash_rel)
    if isinstance(entry, str):
        return entry
    src, troot, trash_rel_actual, orig_rel = entry
    if not is_within_any(os.path.join(mv, orig_rel), allowed_dirs):
        return NOTE_DENIED
    try:
        with get_file_lock(src):
            os.remove(src)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    return ""


def purge_all(mv: str, allowed_dirs: list[str]) -> int:
    """Empty the trash of every in-scope note. Returns the count removed."""
    removed = 0
    for row in list_trashed(mv, allowed_dirs):
        if purge(mv, allowed_dirs, row["trash_path"]) == "":
            removed += 1
    return removed
