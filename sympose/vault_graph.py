"""
The nested directory tree for the dashboard's vault browser (`GET
/api/vault/tree`), the persona-scoped graph projection for the Knowledge
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
_NOTE_STEMS_CACHE: dict[tuple[Any, ...], tuple[float, set[str]]] = {}


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


def _vault_note_stems(mv: str) -> set[str]:
    """Filename stems of every note anywhere in the vault — a filename-only
    walk (no note is opened or held in memory), same ignore list and
    extensions as the content snapshot, mtime-cached like it. Lets a
    restricted persona's graph tell "a link to a hidden note" from "a
    genuinely broken link" without loading the whole vault's text."""
    ignore_dirs = {d.lower() for d in IGNORE_FOLDERS}

    def build() -> set[str]:
        stems: set[str] = set()
        for root, subdirs, files in os.walk(mv):
            subdirs[:] = [
                d for d in subdirs if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            stems.update(
                os.path.splitext(f)[0]
                for f in files
                if f.endswith((".md", ".markdown", ".txt"))
            )
        return stems

    return vault_paths.mtime_cached(_NOTE_STEMS_CACHE, [mv], ignore_dirs, build)


def _scope_prefixes(mv: str, allowed_dirs: list[str]) -> list[str]:
    """Vault-relative folder prefixes a persona may see, or `[""]` when its
    scope is the whole vault."""
    mv_real = os.path.realpath(mv)
    prefixes: list[str] = []
    for d in allowed_dirs:
        d_real = os.path.realpath(d)
        if d_real == mv_real:
            return [""]
        prefixes.append(os.path.relpath(d_real, mv_real).replace(os.sep, "/"))
    return prefixes


def get_vault_tree(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Nested `VaultNode` directory tree for `GET /api/vault/tree`, scoped
    to the persona's allowed folders. Rebuilt fresh from disk on every call
    (no persisted manifest cache — see `vault_manifest_build`'s module
    docstring); `[]` with no vault or no readable folders."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return []
    mv, allowed_dirs = scope

    prefixes = _scope_prefixes(mv, allowed_dirs)
    manifest = vault_manifest_build.build(mv, get_vault_snapshot(mv, allowed_dirs))
    real_folders = _list_real_folders(mv, allowed_dirs)
    return vault_tree.build_tree(
        manifest.get("nodes", []), prefixes, real_folders, manifest.get("links", [])
    )


def _label(n: dict[str, Any]) -> str:
    raw = str(n.get("title") or n["id"]).strip()
    return raw if len(raw) <= 64 else raw[:63].rstrip() + "…"


def get_vault_graph(profile: dict[str, Any]) -> dict[str, Any]:
    """`NebulaGraph`-shaped projection of the vault manifest for `GET
    /api/vault/graph`, scoped to the persona's allowed folders (ADR 010):
    nodes `{id, label, folder, tags, val, exists}` (`val` = link degree +
    1, scales the node radius), links `{source, target}`. `{nodes: [],
    links: []}` with no vault.

    Built from only the notes the persona can see, so a bare `[[Name]]`
    resolves among visible notes (a same-named note in a hidden folder
    can't capture the link), and node size counts only visible links. The
    one thing a scoped build gets wrong is that a link from a visible note
    to a *hidden* one is unresolved and would become a ghost node named
    after the hidden note — so any ghost whose name matches a note that
    exists anywhere in the vault (`_vault_note_stems`) is dropped with its links. What remains
    are genuinely broken links."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return {"nodes": [], "links": []}
    mv, allowed_dirs = scope
    manifest = vault_manifest_build.build(mv, get_vault_snapshot(mv, allowed_dirs))
    all_nodes = manifest.get("nodes", [])
    links = manifest.get("links", [])

    if _scope_prefixes(mv, allowed_dirs) != [""]:
        hidden_stems = _vault_note_stems(mv)
        ghosts = {
            n["id"]
            for n in all_nodes
            if not n.get("exists", True) and n["id"] in hidden_stems
        }
        if ghosts:
            all_nodes = [n for n in all_nodes if n["id"] not in ghosts]
            links = [link for link in links if link["target"] not in ghosts]

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
        for n in all_nodes
    ]
    return {"nodes": nodes, "links": links}
