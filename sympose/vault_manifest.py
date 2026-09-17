"""
Materialized structural map of the vault (ADR-078) — a projection, not the
source of truth: every rebuild reads disk and the `.md` files always win. One
JSON file per master vault, under the *workspace* (never inside the Obsidian
vault) at `.vault_index/<hash>.manifest.json`: nodes, resolved `[[wikilink]]`
links, a folder->count map; no note bodies (navigation and the dashboard graph,
not grounding). Freshness is access-triggered — a cheap top-level-dir mtime gate
serves the cached file untouched; only drift rebuilds (per-vault lock, atomic
write). `patch_note` absorbs Sympose's own writes, re-stamping the watermark so
the next `ensure_fresh` is a no-op.

The pure projection (`build`) and the ADR-078.4 delta core (`_delta_rebuild`)
live in `vault_manifest_build.py`; this module owns the on-disk lifecycle.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from sympose import vault_paths
from sympose.compactor import get_or_create_lock
from sympose.vault_manifest_build import (
    SCHEMA_VERSION,
    _delta_rebuild,
    _mtime_of,
    _node,
    _resolve_links,
    _targets_in,
    build,
)

log = logging.getLogger(__name__)

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_mem_cache: dict[str, dict] = {}
_last_check: dict[str, float] = {}


def _lock_for(path: str) -> threading.Lock:
    return get_or_create_lock(_locks, _locks_guard, path)


def manifest_path(workspace_dir: str, mv: str) -> str:
    digest = hashlib.sha1(os.path.abspath(mv).encode("utf-8")).hexdigest()[:16]
    d = os.path.join(workspace_dir, ".vault_index")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{digest}.manifest.json")


def _top_level_watermark(mv: str, ignore: set) -> float:
    """D6: delegates to `vault_paths.dirs_mtime`, which folds every tracked
    note's own mtime into the watermark - not just each directory's, which
    never moves when an existing file's content changes, only when an entry
    is added/removed/renamed."""
    return vault_paths.dirs_mtime([mv], ignore)


def _load_file(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_atomic_text(path: str, content: str) -> None:
    """Writes `content` to `path` via a tmp file + `os.replace` — the rename
    is atomic on the same filesystem, so a crash mid-write can't leave
    `path` truncated. D1: shared with `vault_write.py`'s note writers
    (`write_note`/`overwrite_note`/`create_note`), which used to write in
    place directly. Raises on failure — a note write reports the error back
    to the caller rather than silently pretending it succeeded (see
    `_write_atomic` below for the best-effort wrapper manifest writes use
    instead, which tolerate a lost update)."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_atomic(path: str, manifest: dict) -> None:
    try:
        write_atomic_text(
            path, json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
        )
    except OSError:
        log.debug("[vault_manifest] atomic write failed for %s", path, exc_info=True)


def load(workspace_dir: str, mv: str) -> dict | None:
    """Last-written manifest, no freshness check. None if never built."""
    path = manifest_path(workspace_dir, mv)
    return _mem_cache.get(path) or _load_file(path)


def _ignore_changed(m: dict, ignore_key: list[str]) -> bool:
    # A changed ignore list doesn't reliably move any directory's own
    # mtime (a newly-unignored folder can easily be *older* than whatever
    # else last touched the vault) - the watermark alone can silently miss
    # this, so the resolved ignore set is compared directly against what
    # the cached manifest was built with. Live bug: removing "Movies" from
    # vault.ignore_folders never surfaced it in folder discovery, because
    # nothing else in the vault had changed since the stale manifest was
    # built.
    return m.get("meta", {}).get("ignore_folders") != ignore_key


def _schema_stale(m: dict) -> bool:
    # D2: same rationale as _ignore_changed - a pre-existing manifest
    # written under an older schema (bare-stem node ids, no target_stem)
    # can have a watermark that still matches if nothing on disk has
    # changed since, so the watermark check alone would serve it forever
    # without ever migrating to the current scheme.
    return m.get("meta", {}).get("schema_version") != SCHEMA_VERSION


def _is_manifest_current(m: dict | None, wm: float, ignore_key: list[str]) -> bool:
    """True when a cached/loaded manifest still matches the vault's current
    watermark, ignore-folder set, and schema — the three independent
    reasons a manifest can go stale (see `_ignore_changed`/`_schema_stale`
    for why the watermark alone can miss the latter two)."""
    return (
        m is not None
        and m.get("meta", {}).get("watermark") == wm
        and not _ignore_changed(m, ignore_key)
        and not _schema_stale(m)
    )


def _try_delta_rebuild(
    mv: str,
    current: dict | None,
    ignore: set,
    ignore_key: list[str],
    read_notes: Callable[[list[str]], list[dict[str, Any]]] | None,
) -> dict | None:
    """An ADR-078.4 delta rebuild when a prior manifest exists under the
    current schema with an unchanged ignore set — None (meaning "do a full
    rebuild instead") if that doesn't hold, or on any delta-rebuild
    failure. A changed ignore set can add or remove whole subtrees a
    stat-only delta never walks into, so that always forces a full rebuild
    rather than trying to make the delta path handle it."""
    if current is None or _ignore_changed(current, ignore_key):
        return None
    if (
        read_notes is None
        or current.get("meta", {}).get("schema_version") != SCHEMA_VERSION
    ):
        return None
    try:
        return _delta_rebuild(mv, current, ignore, read_notes)
    except Exception:
        log.debug(
            "[vault_manifest] delta rebuild failed for %s; full rebuild",
            mv,
            exc_info=True,
        )
        return None


def _finalize_manifest(
    manifest: dict, wm: float, ignore_key: list[str], max_nodes: int
) -> dict:
    manifest["meta"]["watermark"] = wm
    manifest["meta"]["ignore_folders"] = ignore_key
    if max_nodes and len(manifest["nodes"]) > max_nodes:
        manifest["nodes"] = manifest["nodes"][:max_nodes]
        manifest["meta"]["truncated"] = True
    return manifest


def ensure_fresh(
    workspace_dir: str,
    mv: str,
    snapshot_provider: Callable[[], list[dict[str, Any]]],
    *,
    read_notes: Callable[[list[str]], list[dict[str, Any]]] | None = None,
    ignore_folders: list[str] | None = None,
    debounce: float = 2.0,
    max_nodes: int = 0,
) -> dict | None:
    """The manifest, refreshed only on top-level mtime drift. With a prior
    manifest and a `read_notes` reader, the refresh is an ADR-078.4 delta — a
    stat-only walk plus a re-parse of just the changed notes; otherwise a full
    `build()`. Best-effort: the last good manifest (or None) on failure."""
    path = manifest_path(workspace_dir, mv)
    ignore = {str(d).lower().strip() for d in (ignore_folders or [])}
    ignore_key = sorted(ignore)
    now = time.time()

    cached = _mem_cache.get(path)
    if (
        cached is not None
        and debounce > 0
        and (now - _last_check.get(path, 0.0)) < debounce
        and not _ignore_changed(cached, ignore_key)
        and not _schema_stale(cached)
    ):
        return cached
    _last_check[path] = now

    wm = _top_level_watermark(mv, ignore)
    current = cached or _load_file(path)
    if _is_manifest_current(current, wm, ignore_key):
        _mem_cache[path] = current
        return current

    with _lock_for(path):
        current = _mem_cache.get(path) or _load_file(path)
        if _is_manifest_current(current, wm, ignore_key):
            _mem_cache[path] = current
            return current

        manifest = _try_delta_rebuild(mv, current, ignore, ignore_key, read_notes)
        if manifest is None:
            try:
                manifest = build(mv, snapshot_provider())
            except Exception:
                log.debug("[vault_manifest] rebuild failed for %s", mv, exc_info=True)
                return current
        manifest = _finalize_manifest(manifest, wm, ignore_key, max_nodes)
        _write_atomic(path, manifest)
        _mem_cache[path] = manifest
        return manifest


def patch_note(
    workspace_dir: str,
    mv: str,
    rel_path: str,
    meta: dict[str, Any],
    full_content: str,
    *,
    ignore_folders: list[str] | None = None,
) -> None:
    """Single-node upsert after a Sympose write, re-stamping the watermark so
    the next `ensure_fresh` skips the walk. No-op until a manifest exists."""
    path = manifest_path(workspace_dir, mv)
    ignore = {str(d).lower().strip() for d in (ignore_folders or [])}
    with _lock_for(path):
        m = _mem_cache.get(path) or _load_file(path)
        if m is None:
            return
        if m.get("meta", {}).get("schema_version") != SCHEMA_VERSION:
            # D2: an old-schema manifest's node ids/links aren't in a shape
            # this can patch incrementally - leave it alone; the next
            # ensure_fresh call does a full rebuild under the current schema.
            return
        node_id = rel_path.replace("\\", "/")
        real_nodes = {
            n["id"]: n for n in m["nodes"] if n.get("exists") and n["id"] != node_id
        }
        real_nodes[node_id] = _node(
            rel_path,
            meta or {},
            full_content,
            _mtime_of(os.path.join(mv, rel_path), time.time()),
        )
        raw_links = [
            {"source": link["source"], "target_stem": link["target_stem"]}
            for link in m.get("links", [])
            if link["source"] != node_id
        ]
        raw_links += [
            {"source": node_id, "target_stem": t} for t in _targets_in(full_content)
        ]
        # D2/D3: re-resolved against the *current* full node set, not just
        # this note's own links - patching in a note can also change how an
        # unrelated note's already-recorded bare wikilink resolves (e.g.
        # this note is a new same-stem match that makes it ambiguous).
        links, ghosts = _resolve_links(list(real_nodes.values()), raw_links)
        m["nodes"] = list(real_nodes.values()) + ghosts
        m["links"] = links
        m["meta"]["note_count"] = len(real_nodes)
        m["meta"]["generated_at"] = time.time()
        m["meta"]["watermark"] = _top_level_watermark(mv, ignore)
        _write_atomic(path, m)
        _mem_cache[path] = m


def remove_note(
    workspace_dir: str,
    mv: str,
    rel_path: str,
    *,
    ignore_folders: list[str] | None = None,
) -> None:
    """Drop a note's node and its outgoing links after the file is deleted or
    renamed away, re-resolving what remains against the updated node set (a
    remaining link may now resolve to a different real node sharing the
    removed one's stem, or become a ghost if none do). No-op until a
    manifest exists."""
    path = manifest_path(workspace_dir, mv)
    ignore = {str(d).lower().strip() for d in (ignore_folders or [])}
    with _lock_for(path):
        m = _mem_cache.get(path) or _load_file(path)
        if m is None:
            return
        if m.get("meta", {}).get("schema_version") != SCHEMA_VERSION:
            return
        node_id = rel_path.replace("\\", "/")
        real_nodes = [n for n in m["nodes"] if n.get("exists") and n["id"] != node_id]
        raw_links = [
            {"source": link["source"], "target_stem": link["target_stem"]}
            for link in m.get("links", [])
            if link["source"] != node_id
        ]
        # Re-resolving (rather than the old "keep a bare id only while
        # something still points at it" bookkeeping) naturally prunes any
        # ghost this removal orphaned, and re-attaches a remaining link to
        # a *different* real node sharing the removed one's stem if one
        # exists, instead of leaving it pointed at a node that's now gone.
        links, ghosts = _resolve_links(real_nodes, raw_links)
        m["nodes"] = real_nodes + ghosts
        m["links"] = links
        m["meta"]["note_count"] = len(real_nodes)
        m["meta"]["generated_at"] = time.time()
        m["meta"]["watermark"] = _top_level_watermark(mv, ignore)
        _write_atomic(path, m)
        _mem_cache[path] = m
