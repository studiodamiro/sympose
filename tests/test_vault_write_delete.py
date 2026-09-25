"""Deleting a note or folder moves it to `<vault>/.trash/`, never removes it (vault_write_delete).

These tests protect the user's notes: what must survive a delete, what must be refused, and what
the recovery view can find again. Everything runs in a temporary vault."""

import os
import re
import time
import types

import pytest

from sympose import vault_trash, vault_write_delete
from sympose.vault_trash_index import load_index
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND

ALL = {"vault_folders": ["*"]}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return str(root)


def write(vault, rel, text="body"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def trash_files(vault):
    """Every file under `.trash/` as `{trash-relative path: text}` (the clash index excluded)."""
    found = {}
    for root, _, files in os.walk(os.path.join(vault, ".trash")):
        for name in files:
            if name != ".trash-index.json":
                path = os.path.join(root, name)
                found[os.path.relpath(path, os.path.join(vault, ".trash")).replace(os.sep, "/")] = read(path)
    return found


class _FrozenClock:
    """Stands in for the `datetime` module inside vault_write_delete: every call is the same second."""

    class _Now:
        def astimezone(self):
            return self

        def strftime(self, _fmt):
            return "20260101000000"

    datetime = types.SimpleNamespace(now=lambda: _FrozenClock._Now())


# --- delete_note ---------------------------------------------------------------------------


def test_delete_note_moves_it_to_the_bin_with_its_text_and_folder(vault):
    write(vault, "Projects/Atlas.md", "the decision")
    result = vault_write_delete.delete_note(ALL, "Projects/Atlas")
    assert result == f"Moved to the bin: `{os.path.join('.trash', 'Projects', 'Atlas.md')}`"
    assert not os.path.exists(os.path.join(vault, "Projects", "Atlas.md"))
    assert trash_files(vault) == {"Projects/Atlas.md": "the decision"}


def test_delete_note_finds_a_note_by_its_bare_name(vault):
    write(vault, "Deep/Down/Idea.md", "x")
    vault_write_delete.delete_note(ALL, "idea")
    assert list(trash_files(vault)) == ["Deep/Down/Idea.md"]


def test_delete_note_that_does_not_exist_changes_nothing(vault):
    write(vault, "Keep.md", "keep")
    assert vault_write_delete.delete_note(ALL, "Nope") == NOTE_NOT_FOUND
    assert read(os.path.join(vault, "Keep.md")) == "keep"
    assert not os.path.exists(os.path.join(vault, ".trash"))


def test_delete_note_stamps_the_deletion_time_not_the_last_edit(vault):
    path = write(vault, "Old.md")
    long_ago = time.time() - 10 * 365 * 24 * 3600
    os.utime(path, (long_ago, long_ago))
    vault_write_delete.delete_note(ALL, "Old")
    rows = vault_trash.list_trashed(vault, [vault])
    assert len(rows) == 1
    assert time.time() - rows[0]["deleted_at"] < 60


def test_deleting_the_same_path_twice_keeps_both_and_remembers_where_each_came_from(vault):
    write(vault, "Sub/Note.md", "first")
    vault_write_delete.delete_note(ALL, "Sub/Note")
    write(vault, "Sub/Note.md", "second")
    vault_write_delete.delete_note(ALL, "Sub/Note")

    files = trash_files(vault)
    assert sorted(files.values()) == ["first", "second"]
    assert files["Sub/Note.md"] == "first"  # the earlier one is not touched
    (suffixed,) = [name for name in files if name != "Sub/Note.md"]
    assert re.fullmatch(r"Sub/Note-\d{14}\.md", suffixed)
    assert load_index(os.path.join(vault, ".trash")) == {suffixed: "Sub/Note.md"}
    original_paths = sorted(r["original_path"] for r in vault_trash.list_trashed(vault, [vault]))
    assert original_paths == ["Sub/Note.md", "Sub/Note.md"]


def test_deleting_the_same_path_many_times_in_one_second_loses_nothing(vault, monkeypatch):
    monkeypatch.setattr(vault_write_delete, "datetime", _FrozenClock)
    versions = ["one", "two", "three", "four", "five"]
    for version in versions:
        write(vault, "Note.md", version)
        vault_write_delete.delete_note(ALL, "Note")
    assert sorted(trash_files(vault).values()) == sorted(versions)
    rows = vault_trash.list_trashed(vault, [vault])
    assert [r["original_path"] for r in rows] == ["Note.md"] * 5  # each can be restored to where it was


def test_a_note_already_in_the_bin_is_not_deleted_again(vault):
    write(vault, ".trash/Gone.md", "recoverable")
    delete = vault_write_delete.delete_note(ALL, ".trash/Gone")
    assert delete in (NOTE_NOT_FOUND, NOTE_DENIED)
    assert os.path.exists(os.path.join(vault, ".trash", "Gone.md"))
    assert [r["trash_path"] for r in vault_trash.list_trashed(vault, [vault])] == ["Gone.md"]


def test_delete_note_cannot_reach_outside_the_vault(vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("not in the vault")
    assert vault_write_delete.delete_note(ALL, "../outside") == NOTE_NOT_FOUND
    assert outside.read_text() == "not in the vault"


def test_a_restricted_persona_cannot_delete_a_note_outside_its_folders(vault):
    secret = write(vault, "Private/Secret.md", "secret")
    write(vault, "Code/Ok.md", "ok")
    restricted = {"vault_folders": ["Code"]}
    assert vault_write_delete.delete_note(restricted, "Secret") == NOTE_NOT_FOUND
    assert vault_write_delete.delete_note(restricted, "Private/Secret") == NOTE_NOT_FOUND
    assert read(secret) == "secret"
    assert vault_write_delete.delete_note(restricted, "Ok").startswith("Moved to the bin")


def test_delete_note_with_no_vault_configured_is_denied(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    assert vault_write_delete.delete_note(ALL, "Anything") == NOTE_DENIED


def test_delete_note_that_cannot_be_moved_reports_the_error_and_keeps_the_note(vault, monkeypatch):
    path = write(vault, "Stuck.md", "keep me")

    def refuse(*_args):
        raise PermissionError("read-only")

    monkeypatch.setattr(os, "rename", refuse)
    result = vault_write_delete.delete_note(ALL, "Stuck")
    assert result.startswith("Error: Failed to delete note")
    assert read(path) == "keep me"


# --- delete_folder -------------------------------------------------------------------------


def test_delete_folder_moves_the_whole_tree_with_its_files(vault):
    write(vault, "Stuff/a.md", "A")
    write(vault, "Stuff/Inner/b.md", "B")
    result = vault_write_delete.delete_folder(ALL, "Stuff")
    assert result == f"Moved folder to the bin: `{os.path.join('.trash', 'Stuff')}`"
    assert trash_files(vault) == {"Stuff/a.md": "A", "Stuff/Inner/b.md": "B"}
    assert not os.path.exists(os.path.join(vault, "Stuff"))


def test_delete_a_nested_folder_keeps_its_place_in_the_bin(vault):
    write(vault, "Projects/Old/x.md", "x")
    vault_write_delete.delete_folder(ALL, "Projects/Old")
    assert list(trash_files(vault)) == ["Projects/Old/x.md"]
    assert os.path.isdir(os.path.join(vault, "Projects"))


def test_delete_folder_accepts_slashes_and_quotes_around_the_name(vault):
    write(vault, "Stuff/a.md", "A")
    assert vault_write_delete.delete_folder(ALL, "'/Stuff/'").startswith("Moved folder")


def test_delete_folder_that_does_not_exist_is_not_found(vault):
    assert vault_write_delete.delete_folder(ALL, "Nope") == NOTE_NOT_FOUND


def test_delete_folder_refuses_a_file(vault):
    path = write(vault, "Note.md", "text")
    assert vault_write_delete.delete_folder(ALL, "Note.md") == NOTE_NOT_FOUND
    assert read(path) == "text"


@pytest.mark.parametrize("name", ["", "   ", "/", "'/'", ".", "..", "../"])
def test_delete_folder_refuses_blank_root_and_parent_names(vault, name):
    write(vault, "Keep.md", "keep")
    assert vault_write_delete.delete_folder(ALL, name) == NOTE_DENIED
    assert read(os.path.join(vault, "Keep.md")) == "keep"


def test_delete_folder_cannot_reach_outside_the_vault(vault, tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "n.md").write_text("safe")
    assert vault_write_delete.delete_folder(ALL, "../elsewhere") == NOTE_DENIED
    assert (tmp_path / "elsewhere" / "n.md").read_text() == "safe"


def test_a_restricted_persona_cannot_delete_a_folder_outside_its_folders(vault):
    secret = write(vault, "Private/Secret.md", "secret")
    write(vault, "Code/Ok.md", "ok")
    restricted = {"vault_folders": ["Code"]}
    assert vault_write_delete.delete_folder(restricted, "Private") == NOTE_DENIED
    assert read(secret) == "secret"


def test_deleting_a_folder_of_the_same_name_twice_keeps_both(vault):
    write(vault, "Stuff/one.md", "1")
    vault_write_delete.delete_folder(ALL, "Stuff")
    write(vault, "Stuff/two.md", "2")
    vault_write_delete.delete_folder(ALL, "Stuff")
    files = trash_files(vault)
    assert sorted(files.values()) == ["1", "2"]
    assert "Stuff/one.md" in files
    (other,) = [name for name in files if name != "Stuff/one.md"]
    assert re.fullmatch(r"Stuff-\d{14}/two\.md", other)


def test_delete_folder_that_cannot_be_moved_reports_the_error_and_keeps_it(vault, monkeypatch):
    path = write(vault, "Stuck/a.md", "keep me")

    def refuse(*_args):
        raise PermissionError("read-only")

    monkeypatch.setattr(os, "rename", refuse)
    result = vault_write_delete.delete_folder(ALL, "Stuck")
    assert result.startswith("Error: Failed to delete folder")
    assert read(path) == "keep me"


def test_delete_empty_folder_that_cannot_be_removed_reports_the_error(vault, monkeypatch):
    os.makedirs(os.path.join(vault, "Empty"))

    def refuse(_path):
        raise PermissionError("read-only")

    monkeypatch.setattr(os, "rmdir", refuse)
    assert vault_write_delete.delete_folder(ALL, "Empty").startswith("Error: Failed to delete folder")
    assert os.path.isdir(os.path.join(vault, "Empty"))
