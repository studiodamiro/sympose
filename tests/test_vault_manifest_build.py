"""The manifest built from a vault snapshot (`vault_manifest_build`): one node per note, the wikilinks between
them, and a ghost node for a link that points at nothing. The tree, the graph and rename's relinking all
read it, so what counts as a link target, and which note a link means, is pinned here."""

import pytest

from sympose import vault_manifest_build as mb


def entry(rel, body="", meta=None, full=None):
    """A snapshot entry: `full` is the file as stored, `body` what follows its frontmatter."""
    return {"rel_path": rel, "full_content": body if full is None else full, "body": body, "meta": meta or {}, "abs_path": ""}


def build(*entries):
    return mb.build("/vault", list(entries))


def link_pairs(manifest):
    return [(link["source"], link["target"]) for link in manifest["links"]]


def ghosts(manifest):
    return sorted(n["id"] for n in manifest["nodes"] if not n["exists"])


# --- names and tags -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "given, stem",
    [("Note.md", "Note"), ("Folder/Sub/Note.md", "Note"), ("  Note.md  ", "Note"), ("Note", "Note"), ("a.b.md", "a.b")],
)
def test_the_stem_of_a_file_name_or_path(given, stem):
    assert mb._stem(given) == stem


@pytest.mark.parametrize(
    "meta, tags",
    [
        ({"tags": ["a", "#b", " c "]}, ["a", "b", "c"]),
        ({"tags": "a, #b  c"}, ["a", "b", "c"]),
        ({"tags": []}, []),
        ({"tags": ["", "  "]}, []),
        ({"tags": 7}, []),
        ({"tags": None}, []),
        ({}, []),
    ],
)
def test_tags_are_read_from_a_list_or_a_string_and_anything_else_is_none(meta, tags):
    assert mb._tags_of(meta) == tags


# --- which notes a text links to ------------------------------------------------------------


def test_a_link_names_a_note_by_its_stem_whatever_the_folder_heading_or_alias():
    text = "[[Plain]] [[Folder/Deep]] [[Head#Section]] [[Alias|shown]] [[All/Of/It#h|x]]"
    assert mb._targets_in(text) == ["Plain", "Deep", "Head", "Alias", "It"]


def test_text_with_no_links_or_no_text_names_nothing():
    assert mb._targets_in("plain [text] and [one] link") == []
    assert mb._targets_in("") == []
    assert mb._targets_in(None) == []


def test_spaces_around_a_link_target_are_ignored():
    assert mb._targets_in("[[ Note ]] [[  Folder/Deep  ]]") == ["Note", "Deep"]


def test_a_link_with_a_note_extension_names_the_note_without_it():
    assert mb._targets_in("[[Note.md]] [[Other.MD]] [[Old.markdown]] [[Plain.txt]]") == ["Note", "Other", "Old", "Plain"]


def test_a_dot_in_a_note_name_is_part_of_the_name():
    assert mb._targets_in("[[Node.js]] [[v1.2 notes]] [[Dr. Smith]] [[Folder/Vue.js]]") == [
        "Node.js",
        "v1.2 notes",
        "Dr. Smith",
        "Vue.js",
    ]


def test_a_link_to_an_attachment_is_not_a_link_to_a_note():
    text = "![[pic.png]] [[report.PDF]] ![[clip.mp4]] [[Real note]]"
    assert mb._targets_in(text) == ["Real note"]


# --- which note a link means ----------------------------------------------------------------


def node(rel):
    return {"id": rel, "folder": rel.split("/")[0] if "/" in rel else "", "exists": True}


def test_a_unique_name_is_that_note_and_an_unknown_name_is_none():
    by_stem = {"foo": [node("A/Foo.md")]}
    assert mb._pick_link_target("foo", "B", by_stem)["id"] == "A/Foo.md"
    assert mb._pick_link_target("bar", "B", by_stem) is None


def test_a_shared_name_prefers_the_linking_notes_own_top_folder_then_the_first_path():
    by_stem = {"foo": [node("B/Foo.md"), node("A/Foo.md"), node("C/Foo.md")]}
    assert mb._pick_link_target("foo", "C", by_stem)["id"] == "C/Foo.md"
    assert mb._pick_link_target("foo", "Z", by_stem)["id"] == "A/Foo.md"


# --- the manifest ---------------------------------------------------------------------------


def test_each_note_becomes_a_node_with_its_path_folder_tags_title_and_size():
    m = build(
        entry("Top.md", "abc"),
        entry("A/B/Deep.md", "hello", {"title": "A Title", "tags": ["x"]}),
        entry("A/Named.md", "", {"name": "By Name"}),
    )
    top, deep, named = m["nodes"]
    assert (top["id"], top["folder"], top["title"], top["bytes"], top["exists"]) == ("Top.md", "", "Top", 3, True)
    assert (deep["id"], deep["folder"], deep["title"], deep["tags"], deep["bytes"]) == ("A/B/Deep.md", "A", "A Title", ["x"], 5)
    assert named["title"] == "By Name"
    assert m["meta"]["note_count"] == 3
    assert m["meta"]["vault_root"] == "/vault"


def test_two_notes_with_one_name_in_different_folders_stay_two_nodes():
    m = build(entry("A/Same.md"), entry("B/Same.md"))
    assert [n["id"] for n in m["nodes"]] == ["A/Same.md", "B/Same.md"]


def test_folders_are_counted_by_the_notes_below_them():
    m = build(entry("A/one.md"), entry("A/B/two.md"), entry("A/B/three.md"), entry("root.md"))
    assert m["folders"] == {"A": 3, "A/B": 2}


def test_a_link_to_a_note_that_exists_is_an_edge_and_makes_no_ghost():
    m = build(entry("A.md", "see [[B]]"), entry("Sub/B.md"))
    assert link_pairs(m) == [("A.md", "Sub/B.md")]
    assert m["links"][0]["target_stem"] == "B"
    assert ghosts(m) == []


def test_a_link_to_nothing_points_at_a_ghost_named_as_written_and_ghosts_are_not_repeated():
    m = build(entry("A.md", "[[Nowhere]]"), entry("B.md", "[[Nowhere]] and [[Elsewhere]]"))
    assert ghosts(m) == ["Elsewhere", "Nowhere"]
    ghost = next(n for n in m["nodes"] if n["id"] == "Nowhere")
    assert (ghost["exists"], ghost["rel_path"], ghost["title"]) == (False, "", "Nowhere")
    assert link_pairs(m) == [("A.md", "Nowhere"), ("B.md", "Nowhere"), ("B.md", "Elsewhere")]


def test_a_link_reads_the_frontmatter_too_and_may_point_at_its_own_note():
    m = build(entry("A.md", "text", full="---\nrelated: '[[A]]'\n---\ntext"))
    assert link_pairs(m) == [("A.md", "A.md")]


def test_a_note_with_a_dot_in_its_name_is_reached_by_links_to_it():
    m = build(entry("Node.js.md"), entry("Guide.md", "uses [[Node.js]] and [[v1.2 notes]]"), entry("v1.2 notes.md"))
    assert link_pairs(m) == [("Guide.md", "Node.js.md"), ("Guide.md", "v1.2 notes.md")]
    assert ghosts(m) == []


def test_an_embedded_picture_makes_no_ghost_note():
    m = build(entry("A.md", "![[pic.png]] ![[diagram.md]]"), entry("diagram.md"))
    assert link_pairs(m) == [("A.md", "diagram.md")]
    assert ghosts(m) == []


def test_a_link_finds_a_note_whatever_the_case():
    m = build(entry("A.md", "[[foo]] [[BAR]]"), entry("Foo.md"), entry("Sub/bar.md"))
    assert link_pairs(m) == [("A.md", "Foo.md"), ("A.md", "Sub/bar.md")]
    assert ghosts(m) == []


def test_a_name_shared_apart_from_case_prefers_the_linking_notes_folder():
    m = build(entry("A/Note.md", "[[note]]"), entry("A/NOTE.md"), entry("B/note.md"))
    assert m["links"][0]["target"] in ("A/NOTE.md", "A/Note.md")  # the same-folder candidates, not B/note.md
    assert m["links"][0]["target"] != "B/note.md"
