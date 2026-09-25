"""The vault tree the web app's browser shows (`vault_tree.build_tree`, `vault_graph.get_vault_tree`).

Navigation only: which notes and folders a persona sees, in what order, and nothing outside its scope."""

import os

import pytest

from sympose import vault_graph, vault_tree

WHOLE = [""]


def note(rel, tags=(), exists=True, node_id=None):
    return {"id": node_id or rel, "rel_path": rel, "tags": list(tags), "exists": exists}


def build(nodes, prefixes=WHOLE, folders=(), links=()):
    return vault_tree.build_tree(nodes, prefixes, list(folders), list(links))


def names(tree):
    return [n["name"] for n in tree]


# --- shape and order ------------------------------------------------------------------------


def test_notes_are_nested_under_their_folders_with_slash_paths():
    tree = build([note("Projects/Atlas/Plan.md", tags=["x"])])
    (projects,) = tree
    assert (projects["name"], projects["path"], projects["type"]) == ("Projects", "Projects", "folder")
    (atlas,) = projects["children"]
    assert (atlas["name"], atlas["path"]) == ("Atlas", "Projects/Atlas")
    (plan,) = atlas["children"]
    assert plan == {"name": "Plan.md", "path": "Projects/Atlas/Plan.md", "type": "note", "tags": ["x"], "links": []}


def test_folders_come_before_notes_and_each_group_is_sorted_ignoring_case():
    tree = build([note("B.md"), note("a.md"), note("Zeta/n.md"), note("alpha/n.md"), note("Beta/n.md")])
    assert names(tree) == ["alpha", "Beta", "Zeta", "a.md", "B.md"]


def test_backslash_paths_are_read_as_slash_paths():
    tree = build([note("Sub\\Note.md")])
    assert tree[0]["path"] == "Sub"
    assert tree[0]["children"][0]["path"] == "Sub/Note.md"


def test_an_empty_input_is_an_empty_tree():
    assert build([]) == []


# --- what is left out -----------------------------------------------------------------------


def test_ghost_nodes_and_pathless_nodes_are_not_notes_in_the_tree():
    tree = build([note("Real.md"), note("Missing.md", exists=False), {"id": "Ghost", "rel_path": "", "exists": False}])
    assert names(tree) == ["Real.md"]


def test_a_note_with_no_path_is_not_listed_even_if_it_exists():
    assert build([note("", exists=True), {"id": "x", "exists": True}]) == []


def test_a_persona_sees_only_notes_inside_its_folders():
    tree = build([note("Code/A.md"), note("Private/B.md"), note("Root.md")], prefixes=["Code"])
    assert names(tree) == ["Code"]
    assert tree[0]["children"][0]["path"] == "Code/A.md"


def test_a_folder_prefix_does_not_match_a_sibling_sharing_its_name_start():
    tree = build([note("Code/A.md"), note("Code-Archive/Old.md"), note("Codebase.md")], prefixes=["Code"])
    assert [n["path"] for n in tree] == ["Code"]


def test_a_nested_scope_keeps_its_parent_folders_only_as_path_to_the_scope():
    tree = build([note("A/B/In.md"), note("A/Other/Out.md")], prefixes=["A/B"])
    assert tree[0]["path"] == "A"
    assert [c["path"] for c in tree[0]["children"]] == ["A/B"]


def test_several_prefixes_each_let_their_notes_in():
    tree = build([note("One/a.md"), note("Two/b.md"), note("Three/c.md")], prefixes=["One", "Two"])
    assert names(tree) == ["One", "Two"]


# --- empty folders --------------------------------------------------------------------------


def test_a_folder_with_no_notes_still_appears():
    tree = build([note("Notes/a.md")], folders=["Empty", "Notes/Sub/Deeper"])
    assert names(tree) == ["Empty", "Notes"]
    notes_node = tree[1]
    assert names(notes_node["children"]) == ["Sub", "a.md"]
    assert notes_node["children"][0]["children"][0]["path"] == "Notes/Sub/Deeper"


def test_a_real_folder_and_a_notes_parent_are_one_node_not_two():
    tree = build([note("Notes/a.md")], folders=["Notes"])
    assert names(tree) == ["Notes"]
    assert names(tree[0]["children"]) == ["a.md"]


def test_empty_folders_outside_the_scope_or_blank_are_ignored():
    tree = build([], prefixes=["Code"], folders=["Private", "", "/", "Code/Empty", "Code-Archive"])
    assert [n["path"] for n in tree] == ["Code"]
    assert tree[0]["children"][0]["path"] == "Code/Empty"


def test_an_empty_folder_that_is_itself_the_scope_appears():
    assert [n["path"] for n in build([], prefixes=["Code"], folders=["Code"])] == ["Code"]


def test_blank_folder_names_make_no_folder():
    assert build([], folders=["", "/", "//"]) == []


def test_folder_paths_are_tolerant_of_backslashes_and_outer_slashes():
    tree = build([], folders=["/A\\B/"])
    assert tree[0]["path"] == "A"
    assert tree[0]["children"][0]["path"] == "A/B"


# --- links ----------------------------------------------------------------------------------


def test_a_note_lists_what_it_links_to_and_what_links_to_it_by_stem_sorted_without_repeats():
    nodes = [note("A.md", node_id="A"), note("B.md", node_id="B"), note("C.md", node_id="C")]
    links = [
        {"source": "A", "target": "B"},
        {"source": "C", "target": "A"},
        {"source": "A", "target": "B"},
        {"source": "A", "target": "Ghost"},
    ]
    by_name = {n["name"]: n for n in build(nodes, links=links)}
    assert by_name["A.md"]["links"] == ["B", "C", "Ghost"]
    assert by_name["B.md"]["links"] == ["A"]
    assert by_name["C.md"]["links"] == ["A"]


def test_links_with_a_missing_end_are_ignored():
    nodes = [note("A.md", node_id="A")]
    links = [{"source": "A"}, {"target": "A"}, {"source": "", "target": "A"}, {"source": "A", "target": ""}]
    assert build(nodes, links=links)[0]["links"] == []


# --- the tree of a real vault ---------------------------------------------------------------


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return str(root)


def write(vault, rel, text="x"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def paths(tree):
    found = []
    for n in tree:
        found.append(n["path"])
        found.extend(paths(n.get("children", [])))
    return found


def test_a_restricted_personas_tree_holds_none_of_the_hidden_notes_or_folders(vault):
    write(vault, "Code/A.md", "links to [[Secret]]")
    write(vault, "Private/Secret.md", "hidden")
    os.makedirs(os.path.join(vault, "Private", "Empty"))
    os.makedirs(os.path.join(vault, "Code", "EmptyMine"))
    tree = vault_graph.get_vault_tree({"vault_folders": ["Code"]})
    assert sorted(paths(tree)) == ["Code", "Code/A.md", "Code/EmptyMine"]


def test_a_hidden_notes_name_appears_only_as_link_text_in_a_visible_note(vault):
    """The tree never has a node for a hidden note. Its name can only reach the client as the text of a
    link the persona can already read in its own note, so the tree reveals nothing the note does not."""
    write(vault, "Code/A.md", "links to [[Secret]] and [[Nothing]]")
    write(vault, "Private/Secret.md", "hidden")
    tree = vault_graph.get_vault_tree({"vault_folders": ["Code"]})
    (code,) = tree
    (a,) = code["children"]
    assert a["links"] == ["Nothing", "Secret"]  # no way to tell a hidden note from a missing one
    assert "Private" not in paths(tree)


def test_the_whole_vault_persona_sees_everything_and_dot_folders_stay_hidden(vault):
    write(vault, "Code/A.md")
    write(vault, "Private/B.md")
    write(vault, ".trash/Gone.md")
    write(vault, ".obsidian/x.md")
    assert sorted(paths(vault_graph.get_vault_tree({"vault_folders": ["*"]}))) == [
        "Code",
        "Code/A.md",
        "Private",
        "Private/B.md",
    ]


def test_no_vault_configured_is_an_empty_tree(monkeypatch, tmp_path):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    assert vault_graph.get_vault_tree({"vault_folders": ["*"]}) == []
