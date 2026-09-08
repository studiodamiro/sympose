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
"""

import os, re, json, time, hashlib, logging, threading
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")

_locks_guard = threading.Lock()
_locks: Dict[str, threading.Lock] = {}
_mem_cache: Dict[str, dict] = {}
_last_check: Dict[str, float] = {}


def _lock_for(path: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(path, threading.Lock())


def manifest_path(workspace_dir: str, mv: str) -> str:
    digest = hashlib.sha1(os.path.abspath(mv).encode("utf-8")).hexdigest()[:16]
    d = os.path.join(workspace_dir, ".vault_index")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{digest}.manifest.json")


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


def _node(rel_path: str, meta: Dict[str, Any], content: str, mtime: float) -> dict:
    st = _stem(rel_path)
    parts = rel_path.replace("\\", "/").split("/")
    meta = meta or {}
    return {
        "id": st, "rel_path": rel_path, "folder": parts[0] if len(parts) > 1 else "",
        "tags": _tags_of(meta), "title": str(meta.get("title") or meta.get("name") or st),
        "bytes": len(content or ""), "mtime": mtime, "exists": True,
    }


def _mtime_of(path: str, fallback: float = 0.0) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return fallback


def _top_level_watermark(mv: str, ignore: set) -> float:
    dirs = [mv]
    try:
        dirs += [e.path for e in os.scandir(mv)
                 if e.is_dir() and not e.name.startswith(".") and e.name.lower() not in ignore]
    except OSError:
        pass
    return max((_mtime_of(d) for d in dirs), default=0.0)


def _load_file(path: str) -> Optional[dict]:
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


def load(workspace_dir: str, mv: str) -> Optional[dict]:
    """Last-written manifest, no freshness check. None if never built."""
    path = manifest_path(workspace_dir, mv)
    return _mem_cache.get(path) or _load_file(path)


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


def ensure_fresh(
    workspace_dir: str, mv: str, snapshot_provider: Callable[[], List[Dict[str, Any]]],
    *, ignore_folders: Optional[List[str]] = None, debounce: float = 2.0, max_nodes: int = 0,
) -> Optional[dict]:
    """The manifest, rebuilt only on top-level mtime drift. Best-effort: the
    last good manifest (or None) on failure."""
    path = manifest_path(workspace_dir, mv)
    ignore = {str(d).lower().strip() for d in (ignore_folders or [])}
    now = time.time()

    cached = _mem_cache.get(path)
    if cached is not None and debounce > 0 and (now - _last_check.get(path, 0.0)) < debounce:
        return cached
    _last_check[path] = now

    wm = _top_level_watermark(mv, ignore)
    current = cached or _load_file(path)
    if current is not None and current.get("meta", {}).get("watermark") == wm:
        _mem_cache[path] = current
        return current

    with _lock_for(path):
        current = _mem_cache.get(path) or _load_file(path)
        if current is not None and current.get("meta", {}).get("watermark") == wm:
            _mem_cache[path] = current
            return current
        try:
            manifest = build(mv, snapshot_provider())
        except Exception:
            log.debug("[vault_manifest] rebuild failed for %s", mv, exc_info=True)
            return current
        manifest["meta"]["watermark"] = wm
        if max_nodes and len(manifest["nodes"]) > max_nodes:
            manifest["nodes"] = manifest["nodes"][:max_nodes]
            manifest["meta"]["truncated"] = True
        _write_atomic(path, manifest)
        _mem_cache[path] = manifest
        return manifest


def patch_note(
    workspace_dir: str, mv: str, rel_path: str, meta: Dict[str, Any], full_content: str,
    *, ignore_folders: Optional[List[str]] = None,
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
        m["nodes"] = [n for n in m["nodes"] if n["id"] != st]  # drop prior real node or ghost
        m["nodes"].append(_node(rel_path, meta or {}, full_content,
                                _mtime_of(os.path.join(mv, rel_path), time.time())))
        m["links"] = [l for l in m["links"] if l["source"] != st]
        m["links"] += [{"source": st, "target": t} for t in _targets_in(full_content)]
        have = {n["id"] for n in m["nodes"]}
        for l in m["links"]:
            if l["target"] not in have:
                m["nodes"].append({"id": l["target"], "rel_path": "", "folder": "", "tags": [],
                                   "title": l["target"], "bytes": 0, "mtime": 0.0, "exists": False})
                have.add(l["target"])
        m["meta"]["note_count"] = sum(1 for n in m["nodes"] if n.get("exists"))
        m["meta"]["generated_at"] = time.time()
        m["meta"]["watermark"] = _top_level_watermark(mv, ignore)
        _write_atomic(path, m)
        _mem_cache[path] = m
