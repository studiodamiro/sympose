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
from typing import Any, Callable, TypeVar

from sympose.security import is_safe_path

_T = TypeVar("_T")

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


def dirs_mtime(dirs: list[str], ignore: set[str] | None = None) -> float:
    """Mtime watermark shared by every mtime-keyed vault cache (the vault
    content snapshot, the ephemeral manifest build, ...).

    Folds in every tracked note's own mtime, not just each directory's — a
    directory's mtime only moves when an entry is added, removed, or
    renamed inside it, never when an existing file's *content* changes, so
    a watermark built from directory mtimes alone can miss an in-place edit
    indefinitely. Stat-only (opens nothing), so a full recursive walk is
    cheap even at tens of thousands of files. `ignore` (folder names,
    lowercased) skips subtrees like `.trash`/`Attachments` that shouldn't
    force a rebuild when touched."""
    ignore = ignore or set()
    mtime = 0.0
    for d in dirs:
        try:
            mtime = max(mtime, os.path.getmtime(d))
        except OSError:
            pass
        for root, subdirs, files in os.walk(d):
            subdirs[:] = [
                sd
                for sd in subdirs
                if not sd.startswith(".") and sd.lower() not in ignore
            ]
            for sd in subdirs:
                try:
                    mtime = max(mtime, os.path.getmtime(os.path.join(root, sd)))
                except OSError:
                    pass
            for f in files:
                if not f.endswith((".md", ".markdown", ".txt")):
                    continue
                try:
                    mtime = max(mtime, os.stat(os.path.join(root, f)).st_mtime)
                except OSError:
                    pass
    return mtime


def mtime_cached(
    cache: dict[tuple[Any, ...], tuple[float, _T]],
    dirs: list[str],
    ignore: set[str],
    build: Callable[[], _T],
) -> _T:
    """Shared shape for every mtime-keyed vault cache (the content snapshot,
    the real-folders walk, ...): runs `build()` only when `dirs_mtime` has
    moved since the last call for this exact `(dirs, ignore)` scope,
    otherwise reuses the stored result. `cached is not None` — not the
    cached value's truthiness — is what counts as a hit, so a scope with a
    legitimately empty result (no notes, no folders) still gets served from
    cache instead of rebuilding on every single call."""
    cache_key = (tuple(sorted(dirs)), tuple(sorted(ignore)))
    current_mtime = dirs_mtime(dirs, ignore)
    cached = cache.get(cache_key)
    if cached is not None and cached[0] == current_mtime:
        return cached[1]
    value = build()
    cache[cache_key] = (current_mtime, value)
    return value
