"""
The nested directory tree for the dashboard's vault browser (`GET
/api/vault/tree`), the whole-vault graph projection for the Knowledge
Nebula (`GET /api/vault/graph`), plus the mtime-cached real-folder walk
the tree needs so an empty folder still shows up. Navigation only — never
a grounding source; quoted content always comes from the note itself.
"""

import os
from typing import Any

from sympose import vault_manifest_build, vault_paths, vault_tree
from sympose.vault_defaults import IGNORE_FOLDERS
from sympose.vault_snapshot import get_vault_snapshot

_REAL_FOLDERS_CACHE: dict[tuple[Any, ...], tuple[float, list[str]]] = {}


def _list_real_folders(mv: str, dirs: list[str]) -> list[str]:
    """Vault-relative paths of every real subdirectory under `dirs` — a
    directory-only walk (no file reads, same ignore list as the snapshot)
    so `build_tree` can show a folder that exists on disk but holds no
    notes yet. Mtime-cached the same way the snapshot is."""
    ignore_dirs = {d.lower() for d in IGNORE_FOLDERS}

    def build() -> list[str]:
        seen: set = set()
        out: list[str] = []
        for base in dirs:
            if not os.path.exists(base):
                continue
            for root, subdirs, _ in os.walk(base):
                subdirs[:] = [
                    d
                    for d in subdirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for d in subdirs:
                    rel = os.path.relpath(os.path.join(root, d), mv).replace(os.sep, "/")
                    if rel not in seen:
                        seen.add(rel)
                        out.append(rel)
        return out

    return vault_paths.mtime_cached(_REAL_FOLDERS_CACHE, dirs, ignore_dirs, build)


def get_vault_tree(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Nested `VaultNode` directory tree for `GET /api/vault/tree`, scoped
    to the persona's allowed folders. Rebuilt fresh from disk on every call
    (no persisted manifest cache — see `vault_manifest_build`'s module
    docstring); `[]` with no vault or no readable folders."""
    mv = vault_paths.get_master_vault()
    if not mv:
        return []
    allowed_dirs = vault_paths.get_allowed_dirs(profile)
    if not allowed_dirs:
        return []

    mv_real = os.path.realpath(mv)
    prefixes: list[str] = []
    for d in allowed_dirs:
        d_real = os.path.realpath(d)
        if d_real == mv_real:
            prefixes = [""]
            break
        prefixes.append(os.path.relpath(d_real, mv_real).replace(os.sep, "/"))

    manifest = vault_manifest_build.build(mv, get_vault_snapshot(mv, allowed_dirs))
    real_folders = _list_real_folders(mv, allowed_dirs)
    return vault_tree.build_tree(
        manifest.get("nodes", []), prefixes, real_folders, manifest.get("links", [])
    )


def _label(n: dict[str, Any]) -> str:
    raw = str(n.get("title") or n["id"]).strip()
    return raw if len(raw) <= 64 else raw[:63].rstrip() + "…"


def get_vault_graph() -> dict[str, Any]:
    """`NebulaGraph`-shaped projection of the whole-vault manifest for `GET
    /api/vault/graph`: nodes `{id, label, folder, tags, val, exists}` (`val`
    = link degree + 1, scales the node radius), links `{source, target}`.
    Whole-vault and persona-independent — the nebula is an explorer
    surface, not a persona-scoped one. `{nodes: [], links: []}` with no
    vault."""
    mv = vault_paths.get_master_vault()
    if not mv:
        return {"nodes": [], "links": []}
    manifest = vault_manifest_build.build(mv, get_vault_snapshot(mv, [mv]))
    links = manifest.get("links", [])
    degree: dict[str, int] = {}
    for link in links:
        degree[link["source"]] = degree.get(link["source"], 0) + 1
        degree[link["target"]] = degree.get(link["target"], 0) + 1

    nodes = [
        {
            "id": n["id"],
            "label": _label(n),
            "folder": n["folder"],
            "tags": n.get("tags", []),
            "val": degree.get(n["id"], 0) + 1,
            "exists": n.get("exists", True),
        }
        for n in manifest.get("nodes", [])
    ]
    return {"nodes": nodes, "links": links}
