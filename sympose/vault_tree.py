"""
Projection of the manifest — plus a live, directory-only disk listing — into
a nested directory tree for the dashboard's vault browser (`GET
/api/vault/tree`). Navigation only — no note bodies. Persona scoping is
applied here as a vault-relative path-prefix filter, so one whole-vault
manifest still serves a scoped tree.

The manifest alone only knows about notes, so a folder with nothing in it
yet is invisible to a pure manifest projection; `build_tree`'s
`real_folders` argument folds in on-disk directories so an empty folder
still shows up.

The client contract is `VaultNode` in `ui/src/components/sympose/`:
`{name, path, type: "folder" | "note", children?, tags?, links?}` — folders
before notes, each group sorted case-insensitively. `tags` (frontmatter
tags, no leading `#`) and `links` (wikilink neighbours — both outgoing
targets and incoming backlinks, by stem) ride along on note nodes only,
straight from the manifest that's already being read for this call.
"""

from typing import Any


def _within(rel_path: str, prefixes: list[str]) -> bool:
    """True if `rel_path` sits inside one of the allowed vault-relative dir
    prefixes. An empty prefix means whole-vault access."""
    return any(
        p == "" or rel_path == p or rel_path.startswith(p + "/") for p in prefixes
    )


def _link_neighbours(links: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Manifest `links` (`{source, target}`, by stem id) folded into a
    per-stem neighbour list — both directions, so a note's entry covers the
    notes it links out to and the notes that link back to it."""
    out: dict[str, set] = {}
    for link in links:
        s, t = link.get("source"), link.get("target")
        if not s or not t:
            continue
        out.setdefault(s, set()).add(t)
        out.setdefault(t, set()).add(s)
    return {k: sorted(v) for k, v in out.items()}


def _get_or_create_folder(container: dict[str, Any], name: str, path: str) -> dict[str, Any]:
    """Container's per-folder entry (VaultNode + nested children dict),
    creating it on first reference so a `real_folders` entry and a note's
    parent directory both resolve to the same node."""
    entry = container.get(name)
    if entry is None:
        entry = {
            "node": {"name": name, "path": path, "type": "folder", "children": []},
            "children": {},
        }
        container[name] = entry
    return entry["children"]


def _fold_note_nodes(
    roots: dict[str, Any],
    nodes: list[dict[str, Any]],
    allowed_prefixes: list[str],
    neighbours: dict[str, list[str]],
) -> None:
    for n in nodes:
        rel = (n.get("rel_path") or "").replace("\\", "/")
        if not rel or not n.get("exists", True):
            continue
        if not _within(rel, allowed_prefixes):
            continue
        parts = rel.split("/")
        container = roots
        for depth, part in enumerate(parts[:-1]):
            container = _get_or_create_folder(
                container, part, "/".join(parts[: depth + 1])
            )
        container[parts[-1]] = {
            "node": {
                "name": parts[-1],
                "path": rel,
                "type": "note",
                "tags": n.get("tags", []),
                "links": neighbours.get(n.get("id", ""), []),
            },
            "children": {},
        }


def _fold_real_folders(
    roots: dict[str, Any], real_folders: list[str], allowed_prefixes: list[str]
) -> None:
    for rel in real_folders:
        rel = rel.replace("\\", "/").strip("/")
        if not rel or not _within(rel, allowed_prefixes):
            continue
        parts = rel.split("/")
        container = roots
        for depth, part in enumerate(parts):
            container = _get_or_create_folder(
                container, part, "/".join(parts[: depth + 1])
            )


def _emit_tree(container: dict[str, Any]) -> list[dict[str, Any]]:
    folders, notes = [], []
    for entry in container.values():
        node = entry["node"]
        if node["type"] == "folder":
            node["children"] = _emit_tree(entry["children"])
            folders.append(node)
        else:
            notes.append(node)
    folders.sort(key=lambda x: x["name"].lower())
    notes.sort(key=lambda x: x["name"].lower())
    return folders + notes


def build_tree(
    nodes: list[dict[str, Any]],
    allowed_prefixes: list[str],
    real_folders: list[str] = (),
    links: list[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Fold manifest `nodes` into a nested `VaultNode` list, keeping only real
    notes (ghosts — unresolved `[[wikilink]]` targets — carry no `rel_path`)
    whose path is inside `allowed_prefixes`. `real_folders` is a live,
    vault-relative directory listing from disk — folded in the same way so a
    folder with no notes in it still appears."""
    neighbours = _link_neighbours(list(links))
    # folder path -> {"node": <VaultNode dict>, "children": {name -> entry}}
    roots: dict[str, dict[str, Any]] = {}
    _fold_note_nodes(roots, nodes, allowed_prefixes, neighbours)
    _fold_real_folders(roots, real_folders, allowed_prefixes)
    return _emit_tree(roots)
