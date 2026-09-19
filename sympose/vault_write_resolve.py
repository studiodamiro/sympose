"""
Resolving an *existing* note by name to its absolute path (ADR-136, split
out of vault_write.py) — the same three-tier lookup `NoteReadMixin.read_note`
uses, but returning a path rather than content. Shared by
`overwrite_note`/`rename_note`/`delete_note`.
"""

import os
from typing import Any

from sympose import vault_paths
from sympose.config import config_manager, is_safe_path


def _resolve_note_direct(mv: str, allowed_dirs: list[str], clean: str) -> str | None:
    """Case 1 — a direct path under the master vault."""
    direct = os.path.join(mv, clean)
    for allowed in allowed_dirs:
        if is_safe_path(direct, allowed) and os.path.isfile(direct):
            return direct
    return None


def _resolve_note_by_basename(allowed_dirs: list[str], clean: str) -> str | None:
    """Case 2 — the bare filename at an allowed dir's own top level."""
    for allowed in allowed_dirs:
        cand = os.path.join(allowed, os.path.basename(clean))
        if is_safe_path(cand, allowed) and os.path.isfile(cand):
            return cand
    return None


def _resolve_note_recursively(allowed_dirs: list[str], stem: str) -> str | None:
    """Case 3 — a recursive case-insensitive stem match anywhere under an
    allowed dir."""
    raw_ignore = config_manager.get("vault.ignore_folders")
    ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
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
                        return fp
    return None


def resolve_existing_note(profile: dict[str, Any], note_name: str) -> str | None:
    """Absolute path of the file `VaultManager.read_note` would open for
    `note_name`, or `None`: direct path under the master vault → basename in
    an allowed folder → recursive case-insensitive stem match. Shared by
    `overwrite_note` / `rename_note` / `delete_note`."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return None
    clean = note_name.strip().strip("\"'")
    if not clean.endswith(".md"):
        clean += ".md"

    stem = os.path.splitext(os.path.basename(clean))[0].lower()
    return (
        _resolve_note_direct(mv, allowed_dirs, clean)
        or _resolve_note_by_basename(allowed_dirs, clean)
        or _resolve_note_recursively(allowed_dirs, stem)
    )
