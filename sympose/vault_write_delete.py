"""
Deleting a note or folder to `<vault>/.trash/` (ADR-084/ADR-099, split out
of vault_write.py) — recoverable, never a hard delete.
"""

import datetime
import logging
import os
from typing import Any, Callable

from sympose import vault_index, vault_manifest, vault_paths, vault_trash
from sympose.config import config_manager, is_safe_path
from sympose.vault_write_core import _workspace_dir
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND, _NOOP_CALLBACK

log = logging.getLogger(__name__)


def _trash_nonempty_folder(
    mv: str, target_dir: str, clean_name: str
) -> tuple[str | None, str | None]:
    """Moves a non-empty folder to `<vault>/.trash/<name>` (appending a
    timestamp if that name is already taken). Returns (dest, None) on
    success, or (None, error-or-NOTE_DENIED)."""
    dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, clean_name)
    if not is_safe_path(dest, mv):
        return None, NOTE_DENIED
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            dest = f"{dest}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}"
        os.rename(target_dir, dest)
    except OSError as e:
        return None, f"Error: Failed to delete folder: {e}"
    return dest, None


def _deindex_moved_folder_notes(ws: str, mv: str, dest: str, clean_name: str) -> int:
    """De-indexes every note under a folder just moved to the trash.
    Returns how many notes were processed."""
    ignore = config_manager.get("vault.ignore_folders") or []
    note_count = 0
    for root, _, files in os.walk(dest):
        for fn in files:
            if not fn.endswith((".md", ".markdown", ".txt")):
                continue
            sub_rel = os.path.relpath(os.path.join(root, fn), dest)
            orig_rel = os.path.join(clean_name, sub_rel)
            try:
                vault_index.remove_note(ws, mv, orig_rel)
                vault_manifest.remove_note(ws, mv, orig_rel, ignore_folders=ignore)
            except Exception:
                log.debug(
                    "[vault] folder-delete de-index failed for %s",
                    orig_rel,
                    exc_info=True,
                )
            note_count += 1
    return note_count


def delete_folder(
    profile: dict[str, Any],
    folder_name: str,
    *,
    on_backlinks_changed: Callable[[], None] = _NOOP_CALLBACK,
) -> str:
    """Delete a vault folder (ADR-099). An *empty* folder is removed
    outright (`os.rmdir`) — nothing to recover. A folder holding notes
    and/or subfolders moves as one unit to `<vault>/.trash/`, the same
    `os.rename` `delete_note` uses, then every note inside is de-indexed
    individually — the whole subtree drops out of search/the graph while
    it sits in the bin. `vault_trash`'s list/restore/purge need no changes
    for this: each moved note is just another independently recoverable
    row there, and restoring one recreates its parent folder on the way
    back. `NOTE_NOT_FOUND` when the path isn't a real folder, `NOTE_DENIED`
    outside the sandbox."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    clean_name = folder_name.strip().strip("\"'").strip("/\\")
    if not clean_name:
        return NOTE_DENIED
    target_dir = os.path.normpath(os.path.join(mv, clean_name))
    if not any(is_safe_path(target_dir, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED
    if not os.path.isdir(target_dir):
        return NOTE_NOT_FOUND

    rel_display = os.path.relpath(target_dir, mv)
    if not os.listdir(target_dir):
        try:
            os.rmdir(target_dir)
            return f"Deleted empty folder: `{rel_display}`"
        except OSError as e:
            return f"Error: Failed to delete folder: {e}"

    dest, error = _trash_nonempty_folder(mv, target_dir, clean_name)
    if error is not None:
        return error

    ws = _workspace_dir()
    note_count = _deindex_moved_folder_notes(ws, mv, dest, clean_name)
    on_backlinks_changed()
    plural = "s" if note_count != 1 else ""
    dest_rel = os.path.relpath(dest, mv).replace(os.sep, "/")
    return f"Moved folder to the bin: `{dest_rel}` ({note_count} note{plural})"


def delete_note(
    profile: dict[str, Any],
    note_name: str,
    *,
    on_backlinks_changed: Callable[[], None] = _NOOP_CALLBACK,
) -> str:
    """Move a vault note to `<vault>/.trash/` preserving its relative path
    (ADR-084) — recoverable, and `.trash` is already an ignored folder. A
    name clash in the trash gets a timestamp suffix."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return NOTE_DENIED
    src = resolve_existing_note(profile, note_name)
    if src is None:
        return NOTE_NOT_FOUND
    if not any(is_safe_path(src, allowed) for allowed in allowed_dirs):
        return NOTE_DENIED

    old_rel = os.path.relpath(src, mv)
    dest = os.path.join(mv, vault_trash.TRASH_DIRNAME, old_rel)
    # `get_allowed_dirs` only ever returns folders under `mv`, so `old_rel`
    # can't carry a `..` prefix — but assert the trash target stays in-bounds
    # rather than trust that invariant from a distance.
    if not is_safe_path(dest, mv):
        return NOTE_DENIED
    troot = os.path.join(mv, vault_trash.TRASH_DIRNAME)
    clashed = False
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            stem, ext = os.path.splitext(dest)
            dest = f"{stem}-{datetime.datetime.now().astimezone().strftime('%Y%m%d%H%M%S')}{ext}"
            clashed = True
        os.rename(src, dest)
        # `os.rename` keeps the note's own mtime; stamp it to now so the
        # trash view's "deleted N ago" (ADR-085) reflects the deletion, not
        # the last edit.
        os.utime(dest, None)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    if clashed:
        # D4: record the real original path explicitly rather than leaving
        # it to be inferred later from the suffixed filename, which
        # false-positives on a legitimately timestamp-named note.
        dest_rel = os.path.relpath(dest, troot).replace(os.sep, "/")
        vault_trash.record_clash(troot, dest_rel, old_rel)

    ws = _workspace_dir()
    try:
        vault_index.remove_note(ws, mv, old_rel)
        vault_manifest.remove_note(
            ws,
            mv,
            old_rel,
            ignore_folders=config_manager.get("vault.ignore_folders") or [],
        )
    except Exception:
        log.debug("[vault] delete de-index failed for %s", old_rel, exc_info=True)
    on_backlinks_changed()
    return f"Moved to the bin: `{os.path.relpath(dest, mv)}`"
