"""
Resolving an *existing* note to its absolute path. A name with a folder part
is an exact path and resolves only as that path. A bare name is looked up
by name: at an allowed folder's top level (the vault root for an unrestricted
persona), then by a recursive case-insensitive stem match.
"""

import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_defaults import IGNORE_FOLDERS


def _resolve_note_direct(mv: str, allowed_dirs: list[str], clean: str) -> str | None:
    """An exact path under the master vault."""
    direct = os.path.join(mv, clean)
    for allowed in allowed_dirs:
        if is_safe_path(direct, allowed) and os.path.isfile(direct):
            return direct
    return None


def _resolve_note_by_basename(allowed_dirs: list[str], clean: str) -> str | None:
    """A bare filename at an allowed dir's own top level."""
    for allowed in allowed_dirs:
        cand = os.path.join(allowed, os.path.basename(clean))
        if is_safe_path(cand, allowed) and os.path.isfile(cand):
            return cand
    return None


def _resolve_note_recursively(allowed_dirs: list[str], stem: str) -> str | None:
    """A recursive case-insensitive stem match anywhere under an
    allowed dir. When more than one note shares `stem`, resolves
    deterministically to the alphabetically-first path rather than
    whichever the filesystem happens to enumerate first — this call has no
    "source note" to prefer a same-folder match against (unlike
    `vault_manifest_build._pick_link_target`'s identical ambiguity for
    wikilinks), so alphabetical order is the whole tie-break here."""
    ignore_dirs = {d.lower() for d in IGNORE_FOLDERS}
    candidates: list[str] = []
    for allowed in allowed_dirs:
        for root, dirs, files in os.walk(allowed):
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            for fn in files:
                if fn.endswith(".md") and os.path.splitext(fn)[0].lower() == stem:
                    fp = os.path.join(root, fn)
                    if is_safe_path(fp, allowed):
                        candidates.append(fp)
    return min(candidates) if candidates else None


def resolve_existing_note(profile: dict[str, Any], note_name: str) -> str | None:
    """Absolute path of the file for `note_name`, or `None`. A path with a
    folder part (`A/Note`) is exact: it resolves only to that file, never to
    a same-named note elsewhere — a request from a stale tree or a double
    click must not act on a different note. A bare name (`Note`) is looked
    up: at an allowed folder's top level → recursive case-insensitive stem
    match."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    mv, allowed_dirs = scope
    clean = note_name.strip().strip("\"'")
    if not clean.endswith(".md"):
        clean += ".md"

    if "/" in clean:
        return _resolve_note_direct(mv, allowed_dirs, clean)

    stem = os.path.splitext(os.path.basename(clean))[0].lower()
    return _resolve_note_by_basename(allowed_dirs, clean) or _resolve_note_recursively(
        allowed_dirs, stem
    )
