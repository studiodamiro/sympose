"""
Pure projection + delta core for the vault manifest (ADR-078). No file I/O
beyond `stat` — `build()` turns a `_get_vault_snapshot` entry list into the
manifest document, and `_delta_rebuild()` (ADR-078.4) rebuilds one from a prior
manifest by re-parsing only the notes whose mtime moved. The freshness gate,
atomic writes and write-through live in `vault_manifest.py`, which re-exports
`build` so callers keep importing it from there.
"""

import os, re, time, logging
from typing import Any, Callable, Dict, List

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")
_MD_EXT = (".md", ".markdown", ".txt")


def _stem(s: str) -> str:
    return os.path.splitext(os.path.basename(s.strip()))[0]


def _tags_of(meta: Dict[str, Any]) -> List[str]:
    t = meta.get("tags", [])
    if isinstance(t, str):
        return [x.strip().lstrip("#") for x in t.replace(",", " ").split() if x.strip()]
    if isinstance(t, list):
        return [str(x).strip().lstrip("#") for x in t if str(x).strip()]
    return []


def _targets_in(text: str) -> List[str]:
    return [_stem(m.group(1)) for m in _WIKILINK.finditer(text or "")]


def _mtime_of(path: str, fallback: float = 0.0) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return fallback


def _node(rel_path: str, meta: Dict[str, Any], content: str, mtime: float) -> dict:
    st = _stem(rel_path)
    parts = rel_path.replace("\\", "/").split("/")
    meta = meta or {}
    return {
        "id": st, "rel_path": rel_path, "folder": parts[0] if len(parts) > 1 else "",
        "tags": _tags_of(meta), "title": str(meta.get("title") or meta.get("name") or st),
        "bytes": len(content or ""), "mtime": mtime, "exists": True,
    }


def build(mv: str, notes: List[Dict[str, Any]]) -> dict:
    """Pure projection of a `_get_vault_snapshot` entry list. Unresolved
    wikilink targets become ghost nodes (`exists: false`)."""
    nodes: List[dict] = []
    by_stem: Dict[str, dict] = {}
    folders: Dict[str, int] = {}
    links: List[dict] = []
    for e in notes:
        rel = e["rel_path"]
        content = e.get("full_content") or e.get("body") or ""
        node = _node(rel, e.get("meta") or {}, content, _mtime_of(e.get("abs_path") or ""))
        nodes.append(node)
        by_stem[node["id"]] = node
        parts = rel.replace("\\", "/").split("/")
        for d in range(1, len(parts)):
            key = "/".join(parts[:d])
            folders[key] = folders.get(key, 0) + 1
        links += [{"source": node["id"], "target": t} for t in _targets_in(content)]
    ghosts = {l["target"]: {"id": l["target"], "rel_path": "", "folder": "", "tags": [],
                            "title": l["target"], "bytes": 0, "mtime": 0.0, "exists": False}
              for l in links if l["target"] not in by_stem}
    return {
        "meta": {
            "vault_root": os.path.abspath(mv), "generated_at": time.time(),
            "watermark": 0.0, "note_count": len(nodes), "schema_version": SCHEMA_VERSION,
        },
        "nodes": nodes + list(ghosts.values()),
        "links": links,
        "folders": folders,
    }


def _stat_tree(mv: str, ignore: set) -> Dict[str, float]:
    """rel_path -> mtime for every note, stat-only (opens nothing). Cheap even
    at tens of thousands of files — the ADR-078.4 delta-diff surface."""
    out: Dict[str, float] = {}
    for root, dirs, files in os.walk(mv):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ignore]
        for f in files:
            if f.endswith(_MD_EXT):
                p = os.path.join(root, f)
                try:
                    out[os.path.relpath(p, mv).replace(os.sep, "/")] = os.stat(p).st_mtime
                except OSError:
                    pass
    return out


def _delta_rebuild(mv: str, prev: dict, ignore: set,
                   read_notes: Callable[[List[str]], List[Dict[str, Any]]]) -> dict:
    """Rebuild from `prev` by re-parsing only the notes whose mtime moved (plus
    new ones) and dropping deleted ones. Links for surviving notes are carried
    over from `prev`; folders and ghosts are recomputed. Equivalent to a full
    `build()` for the same on-disk state (proven by tests)."""
    prev_real = {n["rel_path"].replace(os.sep, "/"): n for n in prev["nodes"] if n.get("exists")}
    now = _stat_tree(mv, ignore)
    changed = [r for r, mt in now.items()
               if r not in prev_real or abs(float(prev_real[r].get("mtime") or 0.0) - mt) > 1e-6]
    deleted = {r for r in prev_real if r not in now}
    if not changed and not deleted:
        return prev

    entries = read_notes(changed) if changed else []
    dead = set(changed) | deleted
    dead_stems = {_stem(r) for r in dead}

    nodes: Dict[str, dict] = {
        n["id"]: n for n in prev["nodes"]
        if n.get("exists") and n["rel_path"].replace(os.sep, "/") not in dead
    }
    links = [l for l in prev["links"] if l["source"] not in dead_stems]
    for e in entries:
        rel = e["rel_path"]
        content = e.get("full_content") or e.get("body") or ""
        node = _node(rel, e.get("meta") or {}, content,
                     _mtime_of(e.get("abs_path") or os.path.join(mv, rel)))
        nodes[node["id"]] = node
        links += [{"source": node["id"], "target": t} for t in _targets_in(content)]

    folders: Dict[str, int] = {}
    for n in nodes.values():
        parts = n["rel_path"].replace(os.sep, "/").split("/")
        for d in range(1, len(parts)):
            key = "/".join(parts[:d])
            folders[key] = folders.get(key, 0) + 1
    ghosts = {l["target"]: {"id": l["target"], "rel_path": "", "folder": "", "tags": [],
                            "title": l["target"], "bytes": 0, "mtime": 0.0, "exists": False}
              for l in links if l["target"] not in nodes}
    return {
        "meta": {
            "vault_root": os.path.abspath(mv), "generated_at": time.time(),
            "watermark": 0.0, "note_count": len(nodes), "schema_version": SCHEMA_VERSION,
        },
        "nodes": list(nodes.values()) + list(ghosts.values()),
        "links": links,
        "folders": folders,
    }
