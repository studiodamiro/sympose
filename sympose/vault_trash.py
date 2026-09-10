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

import os
import re
import logging
from typing import Any, Dict, List

from sympose.config import is_safe_path

log = logging.getLogger(__name__)

TRASH_DIRNAME = ".trash"

# Sentinels — mapped onto VaultManager.NOTE_* by the thin wrappers in vault.py
# so the server sees one consistent status vocabulary.
NOT_IN_TRASH = "__trash_not_found__"
TARGET_EXISTS = "__trash_target_exists__"
DENIED = "__trash_denied__"

# `delete_note` appends `-YYYYMMDDHHMMSS` before `.md` when a same-named note is
# already in the trash. Strip it to recover the note's original resting place.
_CLASH_SUFFIX_RE = re.compile(r"-\d{14}(?=\.md$)")


def _original_relpath(trash_rel: str) -> str:
    """Vault-relative path the note occupied before deletion — the trash-relative
    path with any `delete_note` clash suffix removed."""
    return _CLASH_SUFFIX_RE.sub("", trash_rel)


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


def list_trashed(mv: str, allowed_dirs: List[str]) -> List[Dict[str, Any]]:
    """Recoverable notes under `<mv>/.trash`, newest deletion first. Each row:
    `{trash_path, original_path, deleted_at (mtime epoch), size}`. Scoped to the
    persona — an entry whose original location sits outside `allowed_dirs` is
    omitted."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    if not os.path.isdir(troot):
        return []
    rows: List[Dict[str, Any]] = []
    for cur, dirs, files in os.walk(troot):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(cur, fn)
            if not is_safe_path(fp, troot):
                continue
            trash_rel = os.path.relpath(fp, troot).replace(os.sep, "/")
            orig_rel = _original_relpath(trash_rel)
            orig_abs = os.path.join(mv, orig_rel)
            if not any(is_safe_path(orig_abs, a) for a in allowed_dirs):
                continue
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rows.append({
                "trash_path": trash_rel,
                "original_path": orig_rel,
                "deleted_at": st.st_mtime,
                "size": st.st_size,
            })
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


def restore(mv: str, allowed_dirs: List[str], trash_rel: str) -> str:
    """Move a trashed note back to its original vault-relative path. Returns that
    path on success, or `NOT_IN_TRASH` / `TARGET_EXISTS` (something occupies the
    original spot now) / `DENIED` / `"Error: …"`."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (DENIED, NOT_IN_TRASH):
        return src

    orig_rel = _original_relpath(os.path.relpath(src, troot).replace(os.sep, "/"))
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
    _prune_empty_dirs(troot, os.path.dirname(src))
    return os.path.relpath(dst, mv).replace(os.sep, "/")


def purge(mv: str, allowed_dirs: List[str], trash_rel: str) -> str:
    """Permanently unlink one trashed note. Returns `""` on success, or
    `NOT_IN_TRASH` / `DENIED` / `"Error: …"`. Scoped: an entry whose original
    location is outside `allowed_dirs` cannot be purged through this persona."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (DENIED, NOT_IN_TRASH):
        return src

    orig_rel = _original_relpath(os.path.relpath(src, troot).replace(os.sep, "/"))
    if not any(is_safe_path(os.path.join(mv, orig_rel), a) for a in allowed_dirs):
        return DENIED
    try:
        os.remove(src)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    _prune_empty_dirs(troot, os.path.dirname(src))
    return ""


def purge_all(mv: str, allowed_dirs: List[str]) -> int:
    """Empty the trash of every in-scope note. Returns the count removed."""
    removed = 0
    for row in list_trashed(mv, allowed_dirs):
        if purge(mv, allowed_dirs, row["trash_path"]) == "":
            removed += 1
    return removed
