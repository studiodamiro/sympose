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

from sympose.compactor import get_or_create_lock
from sympose.vault_manifest_build import (
    SCHEMA_VERSION,
    _delta_rebuild,
    _mtime_of,
    _node,
    _stem,
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
    dirs = [mv]
    try:
        dirs += [
            e.path
            for e in os.scandir(mv)
            if e.is_dir()
            and not e.name.startswith(".")
            and e.name.lower() not in ignore
        ]
    except OSError:
        pass
    return max((_mtime_of(d) for d in dirs), default=0.0)


def _load_file(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_atomic(path: str, manifest: dict) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError:
        log.debug("[vault_manifest] atomic write failed for %s", path, exc_info=True)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def load(workspace_dir: str, mv: str) -> dict | None:
    """Last-written manifest, no freshness check. None if never built."""
    path = manifest_path(workspace_dir, mv)
    return _mem_cache.get(path) or _load_file(path)


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

    def _ignore_changed(m: dict) -> bool:
        # A changed ignore list doesn't reliably move any directory's own
        # mtime (a newly-unignored folder can easily be *older* than
        # whatever else last touched the vault) - the watermark alone can
        # silently miss this, so the resolved ignore set is compared
        # directly against what the cached manifest was built with. Live
        # bug: removing "Movies" from vault.ignore_folders never surfaced
        # it in folder discovery, because nothing else in the vault had
        # changed since the stale manifest was built.
        return m.get("meta", {}).get("ignore_folders") != ignore_key

    cached = _mem_cache.get(path)
    if (
        cached is not None
        and debounce > 0
        and (now - _last_check.get(path, 0.0)) < debounce
        and not _ignore_changed(cached)
    ):
        return cached
    _last_check[path] = now

    wm = _top_level_watermark(mv, ignore)
    current = cached or _load_file(path)
    if (
        current is not None
        and current.get("meta", {}).get("watermark") == wm
        and not _ignore_changed(current)
    ):
        _mem_cache[path] = current
        return current

    with _lock_for(path):
        current = _mem_cache.get(path) or _load_file(path)
        if (
            current is not None
            and current.get("meta", {}).get("watermark") == wm
            and not _ignore_changed(current)
        ):
            _mem_cache[path] = current
            return current

        manifest: dict | None = None
        if (
            current is not None
            and _ignore_changed(current)
        ):
            # A changed ignore set can add or remove whole subtrees a
            # stat-only delta never walks into - always a full rebuild
            # here rather than trying to make the delta path handle it.
            manifest = None
        elif (
            read_notes is not None
            and current is not None
            and current.get("meta", {}).get("schema_version") == SCHEMA_VERSION
        ):
            try:
                manifest = _delta_rebuild(mv, current, ignore, read_notes)
            except Exception:
                log.debug(
                    "[vault_manifest] delta rebuild failed for %s; full rebuild",
                    mv,
                    exc_info=True,
                )
                manifest = None
        if manifest is None:
            try:
                manifest = build(mv, snapshot_provider())
            except Exception:
                log.debug("[vault_manifest] rebuild failed for %s", mv, exc_info=True)
                return current
        manifest["meta"]["watermark"] = wm
        manifest["meta"]["ignore_folders"] = ignore_key
        if max_nodes and len(manifest["nodes"]) > max_nodes:
            manifest["nodes"] = manifest["nodes"][:max_nodes]
            manifest["meta"]["truncated"] = True
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
        st = _stem(rel_path)
        m["nodes"] = [
            n for n in m["nodes"] if n["id"] != st
        ]  # drop prior real node or ghost
        m["nodes"].append(
            _node(
                rel_path,
                meta or {},
                full_content,
                _mtime_of(os.path.join(mv, rel_path), time.time()),
            )
        )
        m["links"] = [link for link in m["links"] if link["source"] != st]
        m["links"] += [{"source": st, "target": t} for t in _targets_in(full_content)]
        have = {n["id"] for n in m["nodes"]}
        for link in m["links"]:
            if link["target"] not in have:
                m["nodes"].append(
                    {
                        "id": link["target"],
                        "rel_path": "",
                        "folder": "",
                        "tags": [],
                        "title": link["target"],
                        "bytes": 0,
                        "mtime": 0.0,
                        "exists": False,
                    }
                )
                have.add(link["target"])
        m["meta"]["note_count"] = sum(1 for n in m["nodes"] if n.get("exists"))
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
    renamed away. Incoming links from other notes are left as-is — they resolve
    to a ghost until those notes are themselves repatched (a rename repatches
    them; a delete leaves the ghost, which is correct). No-op until a manifest
    exists."""
    path = manifest_path(workspace_dir, mv)
    ignore = {str(d).lower().strip() for d in (ignore_folders or [])}
    with _lock_for(path):
        m = _mem_cache.get(path) or _load_file(path)
        if m is None:
            return
        st = _stem(rel_path)
        m["nodes"] = [n for n in m["nodes"] if n["id"] != st]
        m["links"] = [link for link in m["links"] if link["source"] != st]
        # keep a bare id only while something still points at it
        referenced = {link["source"] for link in m["links"]} | {
            link["target"] for link in m["links"]
        }
        m["nodes"] = [n for n in m["nodes"] if n.get("exists") or n["id"] in referenced]
        m["meta"]["note_count"] = sum(1 for n in m["nodes"] if n.get("exists"))
        m["meta"]["generated_at"] = time.time()
        m["meta"]["watermark"] = _top_level_watermark(mv, ignore)
        _write_atomic(path, m)
        _mem_cache[path] = m
