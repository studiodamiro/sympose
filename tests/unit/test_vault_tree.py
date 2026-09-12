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


def test_real_folders_merge_in_empty_directories():
    # ADR-098: an on-disk folder with no notes still shows up, merged
    # alongside note-derived folders rather than replacing them.
    tree = build_tree(NODES, [""], real_folders=["Projects/Creator Studio/Drafts", "Empty"])
    names = [n["name"] for n in tree]
    assert names == ["Empty", "Projects", "Recipes", "top-level.md"]

    empty = tree[0]
    assert empty["type"] == "folder" and empty["children"] == []

    studio = tree[1]["children"][0]
    child_names = [c["name"] for c in studio["children"]]
    assert child_names == ["Drafts", "Pitch.md", "Procedures.md"]
    drafts = studio["children"][0]
    assert drafts["type"] == "folder" and drafts["children"] == []


def test_real_folders_respect_persona_prefix_scoping():
    tree = build_tree(NODES, ["Projects"], real_folders=["Projects/Empty", "Recipes/Empty"])
    names = _all_paths(tree)
    assert "Projects/Empty" in names
    assert "Recipes/Empty" not in names


def test_real_folders_already_present_from_a_note_are_not_duplicated():
    tree = build_tree(NODES, [""], real_folders=["Projects"])
    assert [n["name"] for n in tree] == ["Projects", "Recipes", "top-level.md"]


def test_links_attach_as_wikilink_neighbours_both_directions():
    links = [{"source": "Pitch", "target": "Roadmap"}, {"source": "Idea", "target": "Pitch"}]
    tree = build_tree(NODES, [""], links=links)
    projects = tree[0]
    studio = projects["children"][0]
    pitch = next(c for c in studio["children"] if c["name"] == "Pitch.md")
    # Pitch links out to Roadmap and is linked in from Idea.
    assert pitch["links"] == ["Idea", "Roadmap"]

    roadmap = projects["children"][1]
    assert roadmap["links"] == ["Pitch"]

    grocery = tree[1]["children"][0]
    assert grocery["links"] == []


def _all_paths(tree):
    out = []
    for n in tree:
        out.append(n["path"])
        out.extend(_all_paths(n.get("children", [])))
    return out
