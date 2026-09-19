"""
Pure projection + delta core for the vault manifest (ADR-078). No file I/O
beyond `stat` — `build()` turns a `_get_vault_snapshot` entry list into the
manifest document, and `_delta_rebuild()` (ADR-078.4) rebuilds one from a prior
manifest by re-parsing only the notes whose mtime moved. The freshness gate,
atomic writes and write-through live in `vault_manifest.py`, which re-exports
`build` so callers keep importing it from there.
"""

import logging
import os
import re
import time
from collections.abc import Callable
from typing import Any

from sympose.vault_write_concurrency import current_mtime

log = logging.getLogger(__name__)

# D2: bumped from 1 - node identity moved from bare filename stem to full
# relative path (see _node/_resolve_links below), and each link dict grew a
# `target_stem` field. An old (version-1) cached manifest fails the
# schema_version check in vault_manifest.ensure_fresh and forces a full
# rebuild rather than being reinterpreted under the new scheme.
SCHEMA_VERSION = 2
_WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")
_MD_EXT = (".md", ".markdown", ".txt")


def _stem(s: str) -> str:
    return os.path.splitext(os.path.basename(s.strip()))[0]


def _tags_of(meta: dict[str, Any]) -> list[str]:
    t = meta.get("tags", [])
    if isinstance(t, str):
        return [x.strip().lstrip("#") for x in t.replace(",", " ").split() if x.strip()]
    if isinstance(t, list):
        return [str(x).strip().lstrip("#") for x in t if str(x).strip()]
    return []


def _targets_in(text: str) -> list[str]:
    return [_stem(m.group(1)) for m in _WIKILINK.finditer(text or "")]


def _mtime_of(path: str, fallback: float = 0.0) -> float:
    mtime = current_mtime(path)
    return fallback if mtime is None else mtime


def _node(rel_path: str, meta: dict[str, Any], content: str, mtime: float) -> dict:
    # D2: id is the full relative path, not the bare stem - two notes named
    # the same thing in different folders used to collide on one node,
    # silently dropping one whenever the other was edited/deleted/patched.
    st = _stem(rel_path)
    parts = rel_path.replace("\\", "/").split("/")
    meta = meta or {}
    return {
        "id": rel_path.replace("\\", "/"),
        "rel_path": rel_path,
        "folder": parts[0] if len(parts) > 1 else "",
        "tags": _tags_of(meta),
        "title": str(meta.get("title") or meta.get("name") or st),
        "bytes": len(content or ""),
        "mtime": mtime,
        "exists": True,
    }


def _pick_link_target(
    stem: str, source_folder: str, by_stem: dict[str, list[dict]]
) -> dict | None:
    """Resolves a bare wikilink stem to the real node it most likely refers
    to (D3's identical rationale, applied to the manifest's own link graph).
    Exactly one candidate -> unambiguous. More than one (two notes share a
    name in different folders) -> prefer one in the same top-level folder
    as the linking note - Obsidian's own preference for an unqualified
    link - else the alphabetically-first path: deterministic, and a real
    existing note, instead of the single-node collision a stem-keyed
    identity used to risk. No candidate at all -> None (a ghost node, same
    as before)."""
    candidates = by_stem.get(stem)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    same_folder = [n for n in candidates if n["folder"] == source_folder]
    return same_folder[0] if same_folder else sorted(candidates, key=lambda n: n["id"])[0]


def _resolve_links(
    nodes: list[dict], raw_links: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Turns `{"source": <node id>, "target_stem": <bare wikilink stem>}`
    entries into final `{"source", "target", "target_stem"}` links plus any
    new ghost nodes - `target_stem` survives into the persisted link so a
    later `_delta_rebuild` can always re-resolve from the original bare
    text against the *current* node set, not from a possibly-already-
    resolved `target`."""
    by_stem: dict[str, list[dict]] = {}
    for n in nodes:
        if n.get("exists"):
            by_stem.setdefault(_stem(n["id"]), []).append(n)
    by_id = {n["id"]: n for n in nodes}

    links: list[dict] = []
    ghosts: dict[str, dict] = {}
    for raw in raw_links:
        stem = raw["target_stem"]
        source = by_id.get(raw["source"])
        source_folder = source["folder"] if source else ""
        match = _pick_link_target(stem, source_folder, by_stem)
        links.append(
            {
                "source": raw["source"],
                "target": match["id"] if match else stem,
                "target_stem": stem,
            }
        )
        if match is None:
            ghosts.setdefault(
                stem,
                {
                    "id": stem,
                    "rel_path": "",
                    "folder": "",
                    "tags": [],
                    "title": stem,
                    "bytes": 0,
                    "mtime": 0.0,
                    "exists": False,
                },
            )
    return links, list(ghosts.values())


def build(mv: str, notes: list[dict[str, Any]]) -> dict:
    """Pure projection of a `_get_vault_snapshot` entry list. Unresolved
    wikilink targets become ghost nodes (`exists: false`)."""
    nodes: list[dict] = []
    folders: dict[str, int] = {}
    raw_links: list[dict] = []
    for e in notes:
        rel = e["rel_path"]
        content = e.get("full_content") or e.get("body") or ""
        node = _node(
            rel, e.get("meta") or {}, content, _mtime_of(e.get("abs_path") or "")
        )
        nodes.append(node)
        parts = rel.replace("\\", "/").split("/")
        for d in range(1, len(parts)):
            key = "/".join(parts[:d])
            folders[key] = folders.get(key, 0) + 1
        raw_links += [
            {"source": node["id"], "target_stem": t} for t in _targets_in(content)
        ]
    links, ghosts = _resolve_links(nodes, raw_links)
    return {
        "meta": {
            "vault_root": os.path.abspath(mv),
            "generated_at": time.time(),
            "watermark": 0.0,
            "note_count": len(nodes),
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": nodes + ghosts,
        "links": links,
        "folders": folders,
    }


def _stat_tree(mv: str, ignore: set) -> dict[str, float]:
    """rel_path -> mtime for every note, stat-only (opens nothing). Cheap even
    at tens of thousands of files — the ADR-078.4 delta-diff surface."""
    out: dict[str, float] = {}
    for root, dirs, files in os.walk(mv):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ignore]
        for f in files:
            if f.endswith(_MD_EXT):
                p = os.path.join(root, f)
                try:
                    out[os.path.relpath(p, mv).replace(os.sep, "/")] = os.stat(
                        p
                    ).st_mtime
                except OSError:
                    pass
    return out


def _delta_rebuild(
    mv: str,
    prev: dict,
    ignore: set,
    read_notes: Callable[[list[str]], list[dict[str, Any]]],
) -> dict:
    """Rebuild from `prev` by re-parsing only the notes whose mtime moved (plus
    new ones) and dropping deleted ones. Links for surviving notes are carried
    over from `prev`; folders and ghosts are recomputed. Equivalent to a full
    `build()` for the same on-disk state (proven by tests)."""
    prev_real = {
        n["rel_path"].replace(os.sep, "/"): n for n in prev["nodes"] if n.get("exists")
    }
    now = _stat_tree(mv, ignore)
    changed = [
        r
        for r, mt in now.items()
        if r not in prev_real
        or abs(float(prev_real[r].get("mtime") or 0.0) - mt) > 1e-6
    ]
    deleted = {r for r in prev_real if r not in now}
    if not changed and not deleted:
        return prev

    entries = read_notes(changed) if changed else []
    dead = set(changed) | deleted

    nodes: dict[str, dict] = {
        n["id"]: n
        for n in prev["nodes"]
        if n.get("exists") and n["rel_path"].replace(os.sep, "/") not in dead
    }
    # D2/D3: node id is now the full path, so this comparison is exact -
    # unlike the old stem-based version, it can't drop a surviving,
    # unrelated same-named node's outgoing links by mistake.
    raw_links = [
        {"source": link["source"], "target_stem": link["target_stem"]}
        for link in prev["links"]
        if link["source"] not in dead
    ]
    for e in entries:
        rel = e["rel_path"]
        content = e.get("full_content") or e.get("body") or ""
        node = _node(
            rel,
            e.get("meta") or {},
            content,
            _mtime_of(e.get("abs_path") or os.path.join(mv, rel)),
        )
        nodes[node["id"]] = node
        raw_links += [
            {"source": node["id"], "target_stem": t} for t in _targets_in(content)
        ]

    folders: dict[str, int] = {}
    for n in nodes.values():
        parts = n["rel_path"].replace(os.sep, "/").split("/")
        for d in range(1, len(parts)):
            key = "/".join(parts[:d])
            folders[key] = folders.get(key, 0) + 1

    # Every link is re-resolved against the *current* full node set, not
    # just the newly (re-)parsed ones - adding or removing any note can
    # change how an unrelated, unaffected note's bare wikilink resolves
    # (e.g. a second same-named note appearing elsewhere makes a
    # previously-unambiguous link ambiguous). Pure in-memory - no new I/O,
    # since every node's own data is already in `nodes`.
    links, ghosts = _resolve_links(list(nodes.values()), raw_links)
    return {
        "meta": {
            "vault_root": os.path.abspath(mv),
            "generated_at": time.time(),
            "watermark": 0.0,
            "note_count": len(nodes),
            "schema_version": SCHEMA_VERSION,
        },
        "nodes": list(nodes.values()) + ghosts,
        "links": links,
        "folders": folders,
    }
