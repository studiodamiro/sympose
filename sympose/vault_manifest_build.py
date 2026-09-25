"""
Pure projection of a vault snapshot into the manifest the tree browser
reads: nodes (one per note), links (resolved wikilinks), and folder counts.
No file I/O beyond `stat` — this is rebuilt fresh on every tree request
rather than cached to disk, which is cheap unless the vault is huge, and
keeps this port free of the legacy backend's persisted-manifest/locking
layer (not needed without a search or chat-grounding feature reading it).
"""

import os
import re
import time
from typing import Any

from sympose.vault_defaults import ATTACHMENT_EXTENSIONS, NOTE_EXTENSIONS
from sympose.vault_write_concurrency import current_mtime

_WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")


def _stem(s: str) -> str:
    return os.path.splitext(os.path.basename(s.strip()))[0]


def _tags_of(meta: dict[str, Any]) -> list[str]:
    t = meta.get("tags", [])
    if isinstance(t, str):
        return [x.strip().lstrip("#") for x in t.replace(",", " ").split() if x.strip()]
    if isinstance(t, list):
        return [str(x).strip().lstrip("#") for x in t if str(x).strip()]
    return []


def _link_target(text: str) -> str | None:
    """The note name a wikilink's target text means, or `None` when it names an attachment. Only a
    note extension is dropped (`[[Note.md]]` is `Note`): any other dot is part of the name, so
    `[[Node.js]]` is `Node.js`, which is what the note `Node.js.md` is called."""
    name = os.path.basename(text.strip())
    root, ext = os.path.splitext(name)
    if ext.lower() in ATTACHMENT_EXTENSIONS:
        return None
    return root if ext.lower() in NOTE_EXTENSIONS else name


def _targets_in(text: str) -> list[str]:
    targets = (_link_target(m.group(1)) for m in _WIKILINK.finditer(text or ""))
    return [t for t in targets if t]


def _mtime_of(path: str, fallback: float = 0.0) -> float:
    mtime = current_mtime(path)
    return fallback if mtime is None else mtime


def _node(rel_path: str, meta: dict[str, Any], content: str, mtime: float) -> dict:
    # id is the full relative path, not the bare stem, so two notes named
    # the same thing in different folders don't collide on one node.
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
    to. Exactly one candidate -> unambiguous. More than one (two notes
    share a name in different folders) -> prefer one in the same top-level
    folder as the linking note, else the alphabetically-first path. No
    candidate at all -> None (a ghost node)."""
    candidates = by_stem.get(stem.lower())  # a link finds a note whatever the case, as in Obsidian
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
    new ghost nodes for unresolved targets."""
    by_stem: dict[str, list[dict]] = {}
    for n in nodes:
        if n.get("exists"):
            by_stem.setdefault(_stem(n["id"]).lower(), []).append(n)
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
    """Pure projection of a vault snapshot (see `vault_snapshot.get_vault_snapshot`).
    Unresolved wikilink targets become ghost nodes (`exists: false`)."""
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
            "note_count": len(nodes),
        },
        "nodes": nodes + ghosts,
        "links": links,
        "folders": folders,
    }
