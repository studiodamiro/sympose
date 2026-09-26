"""Reading a note's frontmatter and turning a vault into a snapshot (`vault_snapshot`).

Search, the graph, the tree and the persona's grounding all read the snapshot, so what counts as
frontmatter, and which files become notes, is pinned here."""

import os

import pytest

from sympose.vault_snapshot import get_vault_snapshot, parse_frontmatter

# --- parse_frontmatter ----------------------------------------------------------------------


def test_text_without_frontmatter_is_all_body():
    assert parse_frontmatter("just text\nmore") == ({}, "just text\nmore")


def test_frontmatter_is_read_and_the_body_follows_it():
    meta, body = parse_frontmatter("---\ntitle: Atlas\ntags: [a, b]\ncount: 3\n---\nbody line\n")
    assert meta == {"title": "Atlas", "tags": ["a", "b"], "count": 3}
    assert body == "body line\n"


def test_a_note_that_is_only_frontmatter_has_an_empty_body_with_or_without_a_final_newline():
    assert parse_frontmatter("---\ntitle: T\n---") == ({"title": "T"}, "")
    assert parse_frontmatter("---\ntitle: T\n---\n") == ({"title": "T"}, "")


def test_spaces_after_the_closing_dashes_are_allowed():
    assert parse_frontmatter("---\ntitle: T\n---   \nbody") == ({"title": "T"}, "body")


def test_windows_line_endings_are_allowed():
    assert parse_frontmatter("---\r\ntitle: T\r\n---\r\nbody") == ({"title": "T"}, "body")


@pytest.mark.parametrize(
    "text",
    [
        "---\ntitle: never closed\nbody",  # no closing line
        "----\ntitle: T\n----\nbody",  # four dashes are a rule, not a fence
        "---title: T\n---\nbody",  # the opener has text after it
        "--- \ntitle: T\n---\nbody",  # so does a space
        "\n---\ntitle: T\n---\nbody",  # frontmatter starts on the first line only
        "---\ntitle: T\n--- text on the closing line\nbody",
    ],
)
def test_text_that_only_looks_like_frontmatter_is_all_body(text):
    assert parse_frontmatter(text) == ({}, text)


def test_the_first_closing_line_ends_the_frontmatter_and_later_rules_stay_in_the_body():
    meta, body = parse_frontmatter("---\na: 1\n---\nabove\n---\nbelow\n---\n")
    assert meta == {"a": 1}
    assert body == "above\n---\nbelow\n---\n"


def test_yaml_values_keep_their_types_and_a_key_without_a_value_is_kept_empty():
    meta, _ = parse_frontmatter("---\nflag: true\nnothing:\nnested:\n  a: 1\nlist:\n  - x\n---\n")
    assert meta == {"flag": True, "nothing": None, "nested": {"a": 1}, "list": ["x"]}


def test_broken_yaml_falls_back_to_reading_key_value_lines():
    text = "---\nTitle: 'Quoted'\nkey: [unclosed\n# a comment: not a key\nempty:\nnote: a: b\n---\nbody"
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "Quoted", "key": "[unclosed", "note": "a: b"}  # lowercased, unquoted, no empty or comment
    assert body == "body"


@pytest.mark.parametrize("block", ["- one\n- two", "just words", "# only a comment", "   "])
def test_frontmatter_that_is_not_key_value_gives_no_metadata_but_is_still_removed_from_the_body(block):
    assert parse_frontmatter(f"---\n{block}\n---\nbody") == ({}, "body")


@pytest.mark.xfail(
    strict=True,
    reason="an empty frontmatter block (Obsidian writes one when the last property is deleted) is not recognised, "
    "so its two rules stay in the body",
)
def test_an_empty_frontmatter_block_is_removed_from_the_body():
    assert parse_frontmatter("---\n---\nbody") == ({}, "body")


# --- get_vault_snapshot ---------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path):
    return str(tmp_path)


def write(vault, rel, data="x"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data.encode("utf-8") if isinstance(data, str) else data)
    return path


def snapshot(vault, dirs=None):
    return get_vault_snapshot(vault, dirs or [vault])


def test_each_note_is_an_entry_with_its_path_text_metadata_and_body(vault):
    path = write(vault, "Sub/Note.md", "---\ntitle: T\n---\nbody")
    (entry,) = snapshot(vault)
    assert entry == {
        "file_name": "Note.md",
        "rel_path": os.path.join("Sub", "Note.md"),
        "abs_path": path,
        "full_content": "---\ntitle: T\n---\nbody",
        "meta": {"title": "T"},
        "body": "body",
    }


def test_only_md_files_are_notes_and_they_are_read_in_name_order(vault):
    """`.markdown` and `.txt` files are not notes (#52): they are not read, and so they are not in the tree,
    the graph, the search or the grounding either. The vault health report is where they are mentioned."""
    write(vault, "b.md")
    write(vault, "a.md")
    write(vault, "c.markdown")
    write(vault, "d.txt")
    write(vault, "pic.png")
    write(vault, "data.json")
    assert [e["file_name"] for e in snapshot(vault)] == ["a.md", "b.md"]


def test_ignored_and_hidden_folders_are_left_out(vault):
    write(vault, "Keep/a.md")
    for hidden in (".obsidian", ".git", ".trash", "Attachments", "Drawings", ".anything", "attachments"):
        write(vault, f"{hidden}/x.md")
    write(vault, "Keep/Attachments/deep.md")
    assert [e["rel_path"] for e in snapshot(vault)] == [os.path.join("Keep", "a.md")]


def test_only_the_allowed_folders_are_read_and_paths_stay_relative_to_the_vault(vault):
    write(vault, "Code/a.md")
    write(vault, "Private/b.md")
    entries = snapshot(vault, [os.path.join(vault, "Code")])
    assert [e["rel_path"] for e in entries] == [os.path.join("Code", "a.md")]


def test_an_allowed_folder_that_does_not_exist_is_skipped(vault):
    write(vault, "a.md")
    assert [e["file_name"] for e in snapshot(vault, [os.path.join(vault, "Nope"), vault])] == ["a.md"]


def test_a_symlink_that_leaves_the_allowed_folder_is_not_read(vault, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "Secret.md").write_text("secret")
    write(vault, "a.md")
    os.symlink(outside / "Secret.md", os.path.join(vault, "Link.md"))
    assert [e["file_name"] for e in snapshot(vault)] == ["a.md"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file with no permissions")
def test_an_unreadable_note_is_skipped_and_the_others_are_still_read(vault):
    locked = write(vault, "a.md")
    write(vault, "b.md")
    os.chmod(locked, 0)
    try:
        assert [e["file_name"] for e in snapshot(vault)] == ["b.md"]
    finally:
        os.chmod(locked, 0o644)


def test_a_note_that_is_not_valid_utf8_is_read_with_a_replacement_character(vault):
    write(vault, "a.md", b"caf\xe9 here")
    (entry,) = snapshot(vault)
    assert entry["full_content"] == "caf� here"


@pytest.mark.xfail(
    strict=True,
    reason="a byte order mark (Windows Notepad writes one) is read as text, so `---` is no longer the first "
    "characters and the note's whole frontmatter is treated as body",
)
def test_a_note_that_starts_with_a_byte_order_mark_still_has_its_frontmatter(vault):
    write(vault, "a.md", b"\xef\xbb\xbf---\ntitle: T\n---\nbody")
    (entry,) = snapshot(vault)
    assert entry["meta"] == {"title": "T"}
    assert entry["body"] == "body"
