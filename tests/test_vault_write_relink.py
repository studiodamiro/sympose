"""Renaming a note rewrites the `[[wikilinks]]` that pointed at it, in other notes (vault_write_relink).

This edits many of the user's files in one action, so the tests protect two things: links to the renamed
note are retargeted exactly (heading, alias and embed kept), and nothing else in any file changes.
Everything runs in a temporary vault."""

import os

import pytest

from sympose import vault_write_relink as relink
from sympose import vault_write_rename
from sympose.vault_write_status import NOTE_INVALID_NAME

ALL = {"vault_folders": ["*"]}


def rw(text, old="Old.md", new="New", source="Other.md", same=frozenset()):
    return relink.rewrite_wikilink_targets(text, old, new, source, set(same))


# --- rewrite_wikilink_targets: which links are retargeted -----------------------------------


def test_a_bare_link_is_retargeted_and_counted():
    assert rw("see [[Old]] here") == ("see [[New]] here", 1)


def test_an_embed_keeps_its_bang():
    assert rw("![[Old]]") == ("![[New]]", 1)


def test_a_heading_and_an_alias_are_kept():
    assert rw("[[Old#Section]] [[Old|shown]] [[Old#Section|shown]] ![[Old#Section]]") == (
        "[[New#Section]] [[New|shown]] [[New#Section|shown]] ![[New#Section]]",
        4,
    )


def test_the_match_ignores_case_and_the_new_name_is_written_as_given():
    assert rw("[[old]] [[OLD]]", new="Brand New") == ("[[Brand New]] [[Brand New]]", 2)


def test_links_to_other_notes_and_plain_text_are_left_alone():
    text = "[[Older]] [[Old Note]] [[Newer]] Old and [Old](Old.md) and [[Old"
    assert rw(text) == (text, 0)


def test_text_with_no_links_comes_back_unchanged():
    assert rw("just prose\nover lines\n") == ("just prose\nover lines\n", 0)


def test_a_link_cannot_span_lines():
    text = "[[Old\n]] and [[\nOld]]"
    assert rw(text) == (text, 0)


def test_the_new_name_is_inserted_literally():
    assert rw("[[Old]]", new=r"a\1 (b) $x") == (r"[[a\1 (b) $x]]", 1)


def test_a_markdown_style_link_is_not_touched_only_wikilinks_are():
    assert rw("[Old](Old.md)") == ("[Old](Old.md)", 0)


# --- path-qualified links -------------------------------------------------------------------


def test_a_folder_qualified_link_is_retargeted_only_when_the_folder_matches():
    old = "Projects/Old.md"
    assert rw("[[Projects/Old]]", old=old) == ("[[Projects/New]]", 1)
    assert rw("[[Elsewhere/Old]]", old=old) == ("[[Elsewhere/Old]]", 0)
    assert rw("[[Deep/Projects/Old]]", old=old) == ("[[Deep/Projects/Old]]", 0)


def test_a_qualified_link_to_a_top_level_note_does_not_match():
    assert rw("[[Sub/Old]]", old="Old.md") == ("[[Sub/Old]]", 0)


# --- a bare link when another note has the same name ----------------------------------------


def test_a_bare_link_is_retargeted_from_anywhere_when_the_name_is_unique():
    assert rw("[[Old]]", old="A/Old.md", source="B/x.md") == ("[[New]]", 1)


def test_a_bare_link_is_left_alone_when_another_note_shares_the_name_and_the_source_is_elsewhere():
    same = {"B/Old.md"}
    assert rw("[[Old]]", old="A/Old.md", source="B/x.md", same=same) == ("[[Old]]", 0)


def test_a_bare_link_is_retargeted_when_the_source_sits_in_the_renamed_notes_top_folder():
    same = {"B/Old.md"}
    assert rw("[[Old]]", old="A/Old.md", source="A/x.md", same=same) == ("[[New]]", 1)
    assert rw("[[Old]]", old="A/Old.md", source="A/deeper/x.md", same=same) == ("[[New]]", 1)


def test_a_qualified_link_is_retargeted_even_when_the_name_is_shared():
    same = {"B/Old.md"}
    assert rw("[[A/Old]]", old="A/Old.md", source="B/x.md", same=same) == ("[[A/New]]", 1)
    assert rw("[[B/Old]]", old="A/Old.md", source="B/x.md", same=same) == ("[[B/Old]]", 0)


@pytest.mark.xfail(
    strict=True,
    reason="links inside code fences and inline code are retargeted too, corrupting a code sample "
    "(Obsidian does not treat them as links)",
)
def test_a_link_shown_as_code_is_not_retargeted():
    text = "real [[Old]]\n```\nexample [[Old]]\n```\nand `[[Old]]` inline\n"
    assert rw(text) == ("real [[New]]\n```\nexample [[Old]]\n```\nand `[[Old]]` inline\n", 1)


# --- relink_referencing_notes: the files ----------------------------------------------------


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return str(root)


def write(vault, rel, data):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data.encode("utf-8") if isinstance(data, str) else data)
    return path


def read(path):
    with open(path, "rb") as f:
        return f.read()


def run(vault, refs, old="Old.md", new="New.md", allowed=None, same=frozenset()):
    """What rename_note calls after moving the note: `dst` is where the renamed note now lives."""
    return relink.relink_referencing_notes(
        vault,
        allowed or [vault],
        refs,
        old,
        new,
        os.path.join(vault, new),
        os.path.splitext(os.path.basename(new))[0],
        set(same),
    )


def test_referencing_files_are_rewritten_and_counted(vault):
    a = write(vault, "A.md", "one [[Old]] two")
    b = write(vault, "Sub/B.md", "![[Old#h]]")
    assert run(vault, ["A.md", "Sub/B.md"]) == (2, 0)
    assert read(a) == b"one [[New]] two"
    assert read(b) == b"![[New#h]]"


def test_a_file_with_nothing_to_retarget_is_not_written(vault):
    path = write(vault, "A.md", "[[Other]]")
    long_ago = 1_000_000_000
    os.utime(path, (long_ago, long_ago))
    assert run(vault, ["A.md"]) == (0, 0)
    assert os.stat(path).st_mtime == long_ago


def test_the_renamed_notes_own_links_are_rewritten_at_its_new_path(vault):
    renamed = write(vault, "New.md", "I link to myself: [[Old]]")
    assert run(vault, ["Old.md"]) == (1, 0)  # the backlink list still names the old path
    assert read(renamed) == b"I link to myself: [[New]]"


def test_a_moved_notes_self_link_is_judged_from_its_new_folder(vault):
    """`A/Old.md` becomes `B/New.md` while `C/Old.md` also exists: the note now sits in `B`, so its bare
    `[[Old]]` could mean either and is left alone, as for any other note in a different folder."""
    moved = write(vault, "B/New.md", "[[Old]]")
    assert run(vault, ["A/Old.md"], old="A/Old.md", new="B/New.md", same={"C/Old.md"}) == (0, 0)
    assert read(moved) == b"[[Old]]"


def test_a_file_outside_the_allowed_folders_is_left_alone(vault):
    inside = write(vault, "Code/A.md", "[[Old]]")
    outside = write(vault, "Private/B.md", "[[Old]]")
    assert run(vault, ["Code/A.md", "Private/B.md"], allowed=[os.path.join(vault, "Code")]) == (1, 0)
    assert read(inside) == b"[[New]]"
    assert read(outside) == b"[[Old]]"


def test_a_referencing_file_that_no_longer_exists_is_skipped(vault):
    kept = write(vault, "A.md", "[[Old]]")
    assert run(vault, ["Gone.md", "A.md"]) == (1, 0)
    assert read(kept) == b"[[New]]"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file with no permissions")
def test_a_file_that_cannot_be_read_is_counted_as_failed_and_the_others_still_run(vault):
    locked = write(vault, "A.md", "[[Old]]")
    other = write(vault, "B.md", "[[Old]]")
    os.chmod(locked, 0)
    try:
        assert run(vault, ["A.md", "B.md"]) == (1, 1)
    finally:
        os.chmod(locked, 0o644)
    assert read(locked) == b"[[Old]]"
    assert read(other) == b"[[New]]"


@pytest.mark.xfail(
    strict=True,
    reason="the file is read in text mode, so a Windows (CRLF) note comes back with every line ending changed to LF",
)
def test_line_endings_are_kept(vault):
    path = write(vault, "Crlf.md", b"one\r\nsee [[Old]]\r\nthree\r\n")
    run(vault, ["Crlf.md"])
    assert read(path) == b"one\r\nsee [[New]]\r\nthree\r\n"


@pytest.mark.xfail(
    strict=True,
    reason="the file is read with errors='ignore', so a byte that is not valid UTF-8 is dropped when it is written back",
)
def test_bytes_that_are_not_valid_utf8_are_kept(vault):
    path = write(vault, "Latin1.md", b"caf\xe9 see [[Old]]\n")
    run(vault, ["Latin1.md"])
    assert read(path) == b"caf\xe9 see [[New]]\n"


# --- rename_note end to end -----------------------------------------------------------------


def test_renaming_a_note_retargets_its_backlinks_and_reports_how_many(vault):
    write(vault, "Old.md", "the note")
    a = write(vault, "A.md", "see [[Old]] and [[Old|this]]")
    b = write(vault, "Sub/B.md", "![[Old#Top]]")
    untouched = write(vault, "C.md", "about [[Older]] and Old")
    result = vault_write_rename.rename_note(ALL, "Old", "New")
    assert result == "Renamed to `New.md` (2 files relinked)"
    assert read(a) == b"see [[New]] and [[New|this]]"
    assert read(b) == b"![[New#Top]]"
    assert read(untouched) == b"about [[Older]] and Old"
    assert os.path.exists(os.path.join(vault, "New.md"))


def test_renaming_a_note_with_no_backlinks_reports_no_relink(vault):
    write(vault, "Old.md", "alone")
    assert vault_write_rename.rename_note(ALL, "Old", "New") == "Renamed to `New.md`"


def test_a_bare_link_from_another_folder_is_retargeted_when_the_name_is_unique(vault):
    write(vault, "Notes/Old.md", "the note")
    link = write(vault, "Elsewhere/x.md", "[[Old]]")
    vault_write_rename.rename_note(ALL, "Notes/Old", "New")
    assert read(link) == b"[[New]]"


def test_a_bare_link_to_a_same_named_note_elsewhere_is_left_alone(vault):
    write(vault, "A/Old.md", "the one renamed")
    write(vault, "B/Old.md", "the other")
    from_a = write(vault, "A/x.md", "[[Old]]")
    from_b = write(vault, "B/y.md", "[[Old]]")
    vault_write_rename.rename_note(ALL, "A/Old", "New")
    assert read(from_a) == b"[[New]]"
    assert read(from_b) == b"[[Old]]"  # it may mean B/Old.md: not guessed


def test_a_restricted_persona_leaves_backlinks_outside_its_folders_stale(vault):
    write(vault, "Code/Old.md", "note")
    inside = write(vault, "Code/A.md", "[[Old]]")
    outside = write(vault, "Private/B.md", "[[Old]]")
    vault_write_rename.rename_note({"vault_folders": ["Code"]}, "Code/Old", "New")
    assert read(inside) == b"[[New]]"
    assert read(outside) == b"[[Old]]"


@pytest.mark.parametrize("bad", ["a|b", "a#b", "a[b", "a]b"])
def test_a_new_name_that_would_break_wikilinks_is_refused_and_nothing_changes(vault, bad):
    old = write(vault, "Old.md", "note")
    link = write(vault, "A.md", "[[Old]]")
    assert vault_write_rename.rename_note(ALL, "Old", bad) == NOTE_INVALID_NAME
    assert os.path.exists(old)
    assert read(link) == b"[[Old]]"
