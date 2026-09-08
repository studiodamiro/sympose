"""
Pure projection of the ADR-078 manifest into a nested directory tree for the
dashboard's vault browser (`GET /api/vault/tree`). Navigation only — no note
bodies, same as the manifest it reads from. Persona scoping is applied here as
a vault-relative path-prefix filter, so one whole-vault manifest still serves
both the (unscoped) nebula graph and the (scoped) tree.

The client contract is `VaultNode` in `ui/src/components/sympose/vault-tree.tsx`:
`{name, path, type: "folder" | "note", children?}` — folders before notes, each
group sorted case-insensitively.
"""

from typing import Any, Dict, List


def _within(rel_path: str, prefixes: List[str]) -> bool:
    """True if `rel_path` sits inside one of the allowed vault-relative dir
    prefixes. An empty prefix means whole-vault access."""
    return any(
        p == "" or rel_path == p or rel_path.startswith(p + "/")
        for p in prefixes
    )


def build_tree(nodes: List[Dict[str, Any]], allowed_prefixes: List[str]) -> List[Dict[str, Any]]:
    """Fold manifest `nodes` into a nested `VaultNode` list, keeping only real
    notes (ghosts — unresolved `[[wikilink]]` targets — carry no `rel_path`)
    whose path is inside `allowed_prefixes`."""
    # folder path -> {"node": <VaultNode dict>, "children": {name -> entry}}
    roots: Dict[str, Dict[str, Any]] = {}

    def _folder(container: Dict[str, Any], name: str, path: str) -> Dict[str, Any]:
        entry = container.get(name)
        if entry is None:
            entry = {"node": {"name": name, "path": path, "type": "folder", "children": []}, "children": {}}
            container[name] = entry
        return entry["children"]

    for n in nodes:
        rel = (n.get("rel_path") or "").replace("\\", "/")
        if not rel or not n.get("exists", True):
            continue
        if not _within(rel, allowed_prefixes):
            continue
        parts = rel.split("/")
        container = roots
        for depth, part in enumerate(parts[:-1]):
            container = _folder(container, part, "/".join(parts[: depth + 1]))
        container[parts[-1]] = {
            "node": {"name": parts[-1], "path": rel, "type": "note"},
            "children": {},
        }

    def _emit(container: Dict[str, Any]) -> List[Dict[str, Any]]:
        folders, notes = [], []
        for entry in container.values():
            node = entry["node"]
            if node["type"] == "folder":
                node["children"] = _emit(entry["children"])
                folders.append(node)
            else:
                notes.append(node)
        folders.sort(key=lambda x: x["name"].lower())
        notes.sort(key=lambda x: x["name"].lower())
        return folders + notes

    return _emit(roots)
