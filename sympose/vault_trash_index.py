"""
The `.trash-index.json` sidecar — split out of `vault_trash.py` (project's
200-LOC-per-file guideline).

`vault_write_delete.delete_note` appends `-YYYYMMDDHHMMSS` before `.md` when
a same-named note is already in the trash (`delete_folder` appends it to the
folder's name). Inferring that suffix by
stripping a trailing `-\\d{14}` would false-positive on a legitimately
timestamp-named file (a real `Meeting-20240315120000.md`) — this index
instead *records* the original path explicitly whenever a clash actually
forced a suffix; every other trashed file's trash-relative path already *is*
its original path, so the common case needs no lookup at all.
"""

import json
import os

from sympose.vault_write import get_file_lock

INDEX_FILENAME = ".trash-index.json"


def _index_path(troot: str) -> str:
    return os.path.join(troot, INDEX_FILENAME)


def load_index(troot: str) -> dict[str, str]:
    """The whole clash index, for a caller (e.g. `list_trashed`) that needs
    to look up more than one entry — avoids re-reading the file from disk
    once per lookup the way `original_relpath` alone would."""
    try:
        with open(_index_path(troot), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_index(troot: str, index: dict[str, str]) -> None:
    path = _index_path(troot)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        os.makedirs(troot, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def record_clashes(troot: str, entries: dict[str, str]) -> None:
    """Called by the delete functions only when a same-named clash actually
    forced a timestamp suffix onto a trash path — the non-clash common case
    needs no index entry, since the trash path already equals the original
    path there. Takes several entries at once because a folder moved under a
    suffixed name puts every file inside it under a suffixed path.
    Locks the whole load-mutate-save cycle: locking only the save still lets
    two concurrent clashes both load the same pre-update dict, so whichever
    saves last would silently discard the other's entries."""
    with get_file_lock(_index_path(troot)):
        index = load_index(troot)
        index.update(entries)
        _save_index(troot, index)


def record_clash(troot: str, trash_rel: str, original_rel: str) -> None:
    """`record_clashes` for the one note that `delete_note` just suffixed."""
    record_clashes(troot, {trash_rel: original_rel})


def original_relpath(troot: str, trash_rel: str) -> str:
    """Vault-relative path the note occupied before deletion. Looked up from
    the clash index when `trash_rel` needed a disambiguating suffix;
    otherwise `trash_rel` already *is* the original path."""
    return load_index(troot).get(trash_rel, trash_rel)


def forget_clash(troot: str, trash_rel: str) -> None:
    """Drops `trash_rel`'s index entry once it's restored or purged, so the
    sidecar doesn't accumulate stale rows forever. Same whole-cycle locking
    as `record_clash`."""
    with get_file_lock(_index_path(troot)):
        index = load_index(troot)
        if trash_rel in index:
            del index[trash_rel]
            _save_index(troot, index)
