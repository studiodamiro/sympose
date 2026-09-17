"""
Vault-wide structural views built on top of the ADR-078 manifest: the
force-graph projection for the dashboard's Knowledge Nebula, the
mtime-cached real-folder walk, and the nested directory tree. Navigation
only — never a grounding source; quoted content always comes from the
note itself.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(GraphMixin, ...)` is a pure move, not a
rewrite. Depends on `cls.get_manifest`, `cls._get_master_vault`,
`cls._get_vault_snapshot`, and `cls.get_allowed_dirs`, all of which stay
on `VaultManager` itself — resolved normally through the MRO once
`VaultManager` inherits from this mixin, no parameter threading needed.
"""

import os
from typing import Any

from sympose import vault_manifest, vault_paths, vault_tree
from sympose.config import config_manager

# E8: _list_real_folders' own mtime-keyed cache — it was the one sibling
# directory walk with no cache at all, doing a full uncached walk on every
# dashboard tree request. Same key shape as vault_snapshot.py's own cache.
_REAL_FOLDERS_CACHE: dict[tuple[Any, ...], tuple[float, list[str]]] = {}


class GraphMixin:
    @classmethod
    def get_vault_graph(cls) -> dict[str, Any]:
        """`NebulaGraph`-shaped projection of the manifest for
        `GET /api/vault/graph`: nodes `{id, label, folder, tags, val, exists}`
        (`val` = link degree + 1, scales the node radius), links
        `{source, target}`. `label` is clipped to ~64 chars — a `Quotes/` note
        is named after the whole quote, which is unreadable on a graph node;
        `id` is the node's full vault-relative path (D2) — unique across the
        whole vault, unlike a bare stem, which two same-named notes in
        different folders would otherwise collide on. Falls back to an
        ephemeral in-memory build when `vault.manifest.enabled` is off;
        `{nodes: [], links: []}` with no vault."""
        manifest = cls.get_manifest()
        if manifest is None:
            mv = cls._get_master_vault()
            if not mv:
                return {"nodes": [], "links": []}
            manifest = vault_manifest.build(mv, cls._get_vault_snapshot(mv, [mv]))
        links = manifest.get("links", [])
        degree: dict[str, int] = {}
        for link in links:
            degree[link["source"]] = degree.get(link["source"], 0) + 1
            degree[link["target"]] = degree.get(link["target"], 0) + 1

        def _label(n: dict[str, Any]) -> str:
            raw = str(n.get("title") or n["id"]).strip()
            return raw if len(raw) <= 64 else raw[:63].rstrip() + "…"

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

    @classmethod
    def _list_real_folders(cls, mv: str, dirs: list[str]) -> list[str]:
        """Vault-relative paths of every real subdirectory under `dirs` — a
        directory-only walk (no file reads, same ignore list as
        `_get_vault_snapshot`) so `build_tree` can show a folder that exists
        on disk but holds no notes yet (ADR-098). Mtime-cached (E8) the same
        way `_get_vault_snapshot` is — this was the one sibling walk with no
        cache at all, redone in full on every dashboard tree request."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        cache_key = (tuple(sorted(dirs)), tuple(sorted(ignore_dirs)))
        current_mtime = vault_paths.dirs_mtime(dirs, ignore_dirs)
        cached_mtime, cached_folders = _REAL_FOLDERS_CACHE.get(cache_key, (0.0, []))
        if current_mtime == cached_mtime and cached_folders:
            return cached_folders

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
                    rel = os.path.relpath(os.path.join(root, d), mv).replace(
                        os.sep, "/"
                    )
                    if rel not in seen:
                        seen.add(rel)
                        out.append(rel)
        _REAL_FOLDERS_CACHE[cache_key] = (current_mtime, out)
        return out

    @classmethod
    def get_vault_tree(cls, profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Nested `VaultNode` directory tree for `GET /api/vault/tree`, scoped
        to the persona's allowed folders. Reads the ADR-078 manifest (ephemeral
        in-memory build when `vault.manifest.enabled` is off); `[]` with no
        vault or no readable folders. Navigation only — never grounding."""
        mv = cls._get_master_vault()
        if not mv:
            return []
        allowed_dirs = cls.get_allowed_dirs(profile)
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

        manifest = cls.get_manifest()
        if manifest is None:
            manifest = vault_manifest.build(mv, cls._get_vault_snapshot(mv, [mv]))
        real_folders = cls._list_real_folders(mv, allowed_dirs)
        return vault_tree.build_tree(
            manifest.get("nodes", []), prefixes, real_folders, manifest.get("links", [])
        )
