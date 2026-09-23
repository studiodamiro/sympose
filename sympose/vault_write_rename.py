"""
Renaming a vault note and rewriting every `[[wikilink]]` that pointed at it —
the actual rewrite logic lives in `vault_write_relink.py`.
"""

import os
from typing import Any, Callable

from sympose import vault_backlinks, vault_paths
from sympose.vault_write import get_file_locks
from sympose.vault_write_relink import WIKILINK_UNSAFE_CHARS, relink_referencing_notes
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import (
    NOTE_DENIED,
    NOTE_EXISTS,
    NOTE_INVALID_NAME,
    NOTE_NOT_FOUND,
)


def _dst_already_taken(dst: str, src: str) -> bool:
    """Whether `dst` is occupied by something other than `src` itself (a
    pure case-change, not a real conflict). Race-safe: `os.path.exists`
    and `os.path.samefile` aren't atomic with each other, so either path
    can vanish in the gap between them (a concurrent request touching the
    same note) — caught rather than left to raise `FileNotFoundError`/
    `OSError` across the API boundary, unlike every other failure path in
    this module. Treating a race here as "not a conflict" doesn't lose
    the case where `src` itself vanished: `os.rename` right after this
    check is the actual authoritative operation, and its own `OSError`
    handling already covers that."""
    if not os.path.exists(dst):
        return False
    try:
        return not os.path.samefile(dst, src)
    except OSError:
        return False


def _resolve_rename_destination(
    mv: str, allowed_dirs: list[str], src: str, new_name: str
) -> tuple[str | None, str]:
    """Validates and resolves `new_name`'s destination path for a rename:
    same folder as `src` unless `new_name` itself carries a separator.
    Returns (dst, "") on success, or
    (None, NOTE_DENIED|NOTE_EXISTS|NOTE_INVALID_NAME)."""
    clean_new = new_name.strip().strip("\"'").lstrip("/\\")
    if not clean_new:
        return None, NOTE_DENIED
    if not clean_new.endswith(".md"):
        clean_new += ".md"
    new_stem = os.path.splitext(os.path.basename(clean_new))[0]
    if WIKILINK_UNSAFE_CHARS.intersection(new_stem):
        return None, NOTE_INVALID_NAME
    dst = os.path.normpath(
        os.path.join(mv, clean_new)
        if ("/" in clean_new or "\\" in clean_new)
        else os.path.join(os.path.dirname(src), clean_new)
    )
    if not vault_paths.is_within_any(dst, allowed_dirs):
        return None, NOTE_DENIED
    # A pure case-change (`note.md` -> `Note.md`) resolves `dst` to the same
    # on-disk file as `src` on a case-insensitive filesystem (macOS's
    # default APFS) — `os.path.exists(dst)` is true there even though
    # nothing actually conflicts, so `os.path.samefile` (inode-based, not
    # string-based) is what actually distinguishes "same file, new casing"
    # from "a different file already lives there".
    if _dst_already_taken(dst, src):
        return None, NOTE_EXISTS
    return dst, ""


def rename_note(
    profile: dict[str, Any],
    old_name: str,
    new_name: str,
    *,
    get_backlinks_fn: Callable[
        [dict[str, Any], str], list[dict[str, Any]]
    ] = vault_backlinks.get_backlinks,
    find_notes_by_stem_fn: Callable[
        [dict[str, Any], str], list[str]
    ] = vault_backlinks.find_notes_by_stem,
) -> str:
    """Rename a vault note and rewrite every `[[wikilink]]` that pointed at
    it. `new_name` stays in the same folder unless it carries a separator.
    `NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` as for the other note
    ops."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope
    src = resolve_existing_note(profile, old_name)
    if src is None:
        return NOTE_NOT_FOUND
    # Defense-in-depth re-check, same as `delete_note` — `resolve_existing_note`
    # already gates every path it returns on `is_safe_path`, but a rename
    # shouldn't rely on that invariant alone holding forever.
    if not vault_paths.is_within_any(src, allowed_dirs):
        return NOTE_DENIED

    dst, error = _resolve_rename_destination(mv, allowed_dirs, src, new_name)
    if error:
        return error

    old_rel, new_rel = os.path.relpath(src, mv), os.path.relpath(dst, mv)
    old_stem = os.path.splitext(os.path.basename(src))[0]
    new_stem = os.path.splitext(os.path.basename(dst))[0]
    ref_files = sorted({b["rel_path"] for b in get_backlinks_fn(profile, old_stem)})
    old_rel_norm = old_rel.replace("\\", "/")
    same_stem_paths = {
        p.replace("\\", "/")
        for p in find_notes_by_stem_fn(profile, old_stem)
        if p.replace("\\", "/") != old_rel_norm
    }

    with get_file_locks(src, dst):
        # Re-check under lock: the pre-lock check in
        # `_resolve_rename_destination` is only a fast-path rejection — a
        # concurrent create/rename could have landed on `dst` in between.
        if _dst_already_taken(dst, src):
            return NOTE_EXISTS
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            return f"Error: Failed to rename note: {e}"

    updated, failed = relink_referencing_notes(
        mv, allowed_dirs, ref_files, old_rel, new_rel, dst, new_stem, same_stem_paths
    )

    bits = []
    if updated:
        bits.append(f"{updated} file{'s' if updated != 1 else ''} relinked")
    if failed:
        bits.append(f"{failed} relink{'s' if failed != 1 else ''} failed — see server log")
    tail = f" ({', '.join(bits)})" if bits else ""
    return f"Renamed to `{new_rel}`{tail}"
