"""
Vault root & sandbox path resolution.

Every other vault module resolves "which directories can this persona touch"
through here rather than re-deriving it — `MASTER_VAULT_PATH` is the single
env var naming the vault root, and a persona's own `vault_folders` (or the
legacy singular `vault_folder`) narrows that to a sandboxed subset. Stdlib
only, no dependency on any other vault_*.py module, so nothing else here can
create a circular import.
"""

import logging
import os
from typing import Any

from sympose.config import is_safe_path

log = logging.getLogger(__name__)


def get_master_vault() -> str | None:
    """Absolute, `~`-expanded vault root from `MASTER_VAULT_PATH`, or `None`
    when it isn't set — the one env var naming where a linked vault lives."""
    mv = os.getenv("MASTER_VAULT_PATH")
    return os.path.abspath(os.path.expanduser(mv)) if mv else None


def get_vault_name() -> str | None:
    """Display name for the vault root, for the dashboard's note-path
    breadcrumb — the master vault directory's own basename. `None` when
    `MASTER_VAULT_PATH` isn't set, same contract as `get_master_vault`."""
    mv = get_master_vault()
    return os.path.basename(mv) if mv else None


def get_allowed_dirs(profile: dict[str, Any]) -> list[str]:
    """Sandbox directories this persona may read/write, derived from its
    `vault_folders` (or legacy `vault_folder`) against the vault root. `""`,
    `"*"`, or `"all"` in the list means unrestricted (the whole vault);
    anything else is joined onto the root and must resolve safely under it.
    Falls back to `[mv]` if nothing configured resolves safely, so a
    misconfigured persona never ends up with zero writable directories."""
    mv = get_master_vault()
    if not mv:
        return []
    try:
        os.makedirs(mv, exist_ok=True)
        folders = profile.get("vault_folders") or [profile.get("vault_folder", "")]
        if "" in folders or "*" in folders or "all" in folders:
            return [mv]
        allowed = []
        for f in folders:
            path = os.path.join(mv, f.strip()) if f.strip() else mv
            if is_safe_path(path, mv):
                os.makedirs(path, exist_ok=True)
                allowed.append(path)
        return allowed or [mv]
    except Exception as e:
        log.debug("get_allowed_dirs failed for %s: %s", mv, e)
        return []


def get_primary_dir(profile: dict[str, Any]) -> str | None:
    """The persona's first allowed directory — where a bare (unqualified)
    note name is created, as opposed to an explicit `Folder/Note` path."""
    dirs = get_allowed_dirs(profile)
    return dirs[0] if dirs else None
