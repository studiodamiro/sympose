"""Unit tests for sympose.vault_tree.build_tree — the manifest -> VaultNode
directory-tree projection with persona path-prefix scoping."""

from sympose.vault_tree import build_tree

# A slice of manifest `nodes` — real notes plus one ghost (unresolved wikilink).
NODES = [
    {"id": "Pitch", "rel_path": "Projects/Creator Studio/Pitch.md", "exists": True},
    {"id": "Procs", "rel_path": "Projects/Creator Studio/Procedures.md", "exists": True},
    {"id": "Roadmap", "rel_path": "Projects/Roadmap.md", "exists": True},
    {"id": "Grocery", "rel_path": "Recipes/Grocery.md", "exists": True},
    {"id": "Idea", "rel_path": "top-level.md", "exists": True},
    {"id": "GhostLink", "rel_path": "", "exists": False},
]


def test_builds_nested_tree_folders_before_notes_alpha_sorted():
    tree = build_tree(NODES, [""])
    names = [n["name"] for n in tree]
    # folders (Projects, Recipes) sorted first, then the loose note
    assert names == ["Projects", "Recipes", "top-level.md"]

    projects = tree[0]
    assert projects["type"] == "folder" and projects["path"] == "Projects"
    child_names = [c["name"] for c in projects["children"]]
    assert child_names == ["Creator Studio", "Roadmap.md"]  # subfolder before note

    studio = projects["children"][0]
    assert studio["path"] == "Projects/Creator Studio"
    assert [c["name"] for c in studio["children"]] == ["Pitch.md", "Procedures.md"]
    assert all(c["type"] == "note" for c in studio["children"])


def test_ghost_nodes_are_excluded():
    flat = _all_paths(build_tree(NODES, [""]))
    assert "" not in flat
    assert not any(p == "GhostLink" for p in flat)


def test_persona_prefix_scoping_limits_the_tree():
    tree = build_tree(NODES, ["Projects"])
    assert [n["name"] for n in tree] == ["Projects"]
    # Recipes/ and the loose top-level note are outside the sandbox
    assert "Recipes/Grocery.md" not in _all_paths(tree)
    assert "top-level.md" not in _all_paths(tree)


def test_prefix_matches_on_a_path_boundary_not_a_substring():
    nodes = [
        {"id": "A", "rel_path": "Project Notes/A.md", "exists": True},
        {"id": "B", "rel_path": "Projects/B.md", "exists": True},
    ]
    tree = build_tree(nodes, ["Projects"])
    assert [n["name"] for n in tree] == ["Projects"]


def _all_paths(tree):
    out = []
    for n in tree:
        out.append(n["path"])
        out.extend(_all_paths(n.get("children", [])))
    return out
