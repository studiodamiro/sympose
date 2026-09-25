"""
Deleting a note or folder to `<vault>/.trash/` — recoverable, never a hard
delete.
"""

import datetime
import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_trash import TRASH_DIRNAME
from sympose.vault_trash_index import record_clash
from sympose.vault_write import get_file_locks
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND


def _trash_nonempty_folder(
    target_dir: str, dest: str
) -> tuple[str | None, str | None]:
    """Moves a non-empty folder to `dest` under `<vault>/.trash/` (appending
    a timestamp if that name is already taken) — called with both
    `target_dir` and `dest` already locked by the caller. Returns
    (final dest, None) on success, or (None, error)."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            dest = f"{dest}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
        os.rename(target_dir, dest)
    except OSError as e:
        return None, f"Error: Failed to delete folder: {e}"
    return dest, None


def _unused_name(taken: str) -> str:
    """`taken` with a timestamp before its extension, and a counter after that if even this is
    taken (three deletes of one path in a second): `os.rename` replaces an existing file
    silently, so a name in use must never be chosen."""
    stem, ext = os.path.splitext(taken)
    stamped = f"{stem}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
    candidate, counter = f"{stamped}{ext}", 1
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{stamped}-{counter}{ext}"
    return candidate


def delete_folder(profile: dict[str, Any], folder_name: str) -> str:
    """Delete a vault folder. An *empty* folder is removed outright
    (`os.rmdir`) — nothing to recover. A folder holding notes and/or
    subfolders moves as one unit to `<vault>/.trash/`, the same rename
    `delete_note` uses. `NOTE_NOT_FOUND` when the path isn't a real folder,
    `NOTE_DENIED` outside the sandbox."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope
    clean_name = folder_name.strip().strip("\"'").strip("/\\")
    if not clean_name:
        return NOTE_DENIED
    target_dir = os.path.normpath(os.path.join(mv, clean_name))
    # `clean_name` resolving to the vault root itself (e.g. ".") is never a
    # real folder to delete — `is_safe_path` alone accepts it (target ==
    # base is safe by that check's own definition), so it needs its own
    # explicit rejection here. Likewise `.trash` itself: it's a reserved
    # path, not a folder a persona ever "deletes" — without this, a
    # non-empty `.trash` would attempt an `os.rename` into its own subtree
    # (guaranteed to fail, but with an opaque error) and an empty one would
    # simply be rmdir'd away, silently discarding the whole recovery surface.
    if target_dir in (os.path.normpath(mv), os.path.join(mv, TRASH_DIRNAME)):
        return NOTE_DENIED
    if not vault_paths.is_within_any(target_dir, allowed_dirs):
        return NOTE_DENIED
    if not os.path.isdir(target_dir):
        return NOTE_NOT_FOUND

    # Precomputed so both it and `target_dir` can be locked together, up
    # front — `_trash_nonempty_folder` only ever appends a clash suffix to
    # this exact path, never picks a different base.
    dest = os.path.join(mv, TRASH_DIRNAME, clean_name)
    if not is_safe_path(dest, mv):
        return NOTE_DENIED

    rel_display = os.path.relpath(target_dir, mv)
    with get_file_locks(target_dir, dest):
        if not os.listdir(target_dir):
            try:
                os.rmdir(target_dir)
                return f"Deleted empty folder: `{rel_display}`"
            except OSError as e:
                return f"Error: Failed to delete folder: {e}"

        dest, error = _trash_nonempty_folder(target_dir, dest)
        if error is not None:
            return error
        dest_rel = os.path.relpath(dest, mv).replace(os.sep, "/")
        return f"Moved folder to the bin: `{dest_rel}`"


def delete_note(profile: dict[str, Any], note_name: str) -> str:
    """Move a vault note to `<vault>/.trash/` preserving its relative path —
    recoverable, and `.trash` is already an ignored folder. A name clash in
    the trash gets a timestamp suffix."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope
    src = resolve_existing_note(profile, note_name)
    if src is None:
        return NOTE_NOT_FOUND
    if not vault_paths.is_within_any(src, allowed_dirs):
        return NOTE_DENIED
    # A note already in the bin is not a note to delete: moving it to `.trash/.trash/` would hide it
    # from the recovery view, which skips dot-folders.
    if is_safe_path(src, os.path.join(mv, TRASH_DIRNAME)):
        return NOTE_NOT_FOUND

    old_rel = os.path.relpath(src, mv)
    dest = os.path.join(mv, TRASH_DIRNAME, old_rel)
    if not is_safe_path(dest, mv):
        return NOTE_DENIED
    with get_file_locks(src, dest):
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            clashed = os.path.exists(dest)
            if clashed:
                dest = _unused_name(dest)
            os.rename(src, dest)
            # `os.rename` keeps the note's own mtime; stamp it to now so a
            # future trash view's "deleted N ago" reflects the deletion, not
            # the last edit.
            os.utime(dest, None)
            if clashed:
                troot = os.path.join(mv, TRASH_DIRNAME)
                trash_rel = os.path.relpath(dest, troot).replace(os.sep, "/")
                record_clash(troot, trash_rel, old_rel.replace(os.sep, "/"))
        except OSError as e:
            return f"Error: Failed to delete note: {e}"
    return f"Moved to the bin: `{os.path.relpath(dest, mv)}`"
