"""
Projection of the ADR-078 manifest — plus a live, directory-only disk listing
(ADR-098) — into a nested directory tree for the dashboard's vault browser
(`GET /api/vault/tree`). Navigation only — no note bodies, same as the
manifest it reads from. Persona scoping is applied here as a vault-relative
path-prefix filter, so one whole-vault manifest still serves both the
(unscoped) nebula graph and the (scoped) tree.

The manifest alone only knows about notes, so a folder with nothing in it yet
is invisible to a pure manifest projection; `build_tree`'s `real_folders`
argument folds in on-disk directories (see `VaultManager._list_real_folders`)
so an empty folder still shows up.

The client contract is `VaultNode` in `ui/src/components/sympose/vault-tree.tsx`:
`{name, path, type: "folder" | "note", children?, tags?, links?}` — folders
before notes, each group sorted case-insensitively. `tags` (frontmatter tags,
no leading `#`) and `links` (wikilink neighbours — both outgoing targets and
incoming backlinks, by stem) ride along on note nodes only, straight from the
manifest that's already being read for this call — no extra vault read, no
separate endpoint — so the dashboard's vault search can match on them
client-side.
"""

from typing import Any, Dict, List


def _within(rel_path: str, prefixes: List[str]) -> bool:
    """True if `rel_path` sits inside one of the allowed vault-relative dir
    prefixes. An empty prefix means whole-vault access."""
    return any(
        p == "" or rel_path == p or rel_path.startswith(p + "/")
        for p in prefixes
    )


def _link_neighbours(links: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Manifest `links` (`{source, target}`, by stem id) folded into a
    per-stem neighbour list — both directions, so a note's entry covers the
    notes it links out to and the notes that link back to it."""
    out: Dict[str, set] = {}
    for l in links:
        s, t = l.get("source"), l.get("target")
        if not s or not t:
            continue
        out.setdefault(s, set()).add(t)
        out.setdefault(t, set()).add(s)
    return {k: sorted(v) for k, v in out.items()}


def build_tree(
    nodes: List[Dict[str, Any]],
    allowed_prefixes: List[str],
    real_folders: List[str] = (),
    links: List[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """Fold manifest `nodes` into a nested `VaultNode` list, keeping only real
    notes (ghosts — unresolved `[[wikilink]]` targets — carry no `rel_path`)
    whose path is inside `allowed_prefixes`. `real_folders` (ADR-098) is a
    live, vault-relative directory listing from disk — folded in the same way
    so a folder with no notes in it still appears, instead of being invisible
    because the manifest itself only ever tracks notes."""
    neighbours = _link_neighbours(list(links))
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
            "node": {
                "name": parts[-1], "path": rel, "type": "note",
                "tags": n.get("tags", []), "links": neighbours.get(n.get("id", ""), []),
            },
            "children": {},
        }

    for rel in real_folders:
        rel = rel.replace("\\", "/").strip("/")
        if not rel or not _within(rel, allowed_prefixes):
            continue
        parts = rel.split("/")
        container = roots
        for depth, part in enumerate(parts):
            container = _folder(container, part, "/".join(parts[: depth + 1]))

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
