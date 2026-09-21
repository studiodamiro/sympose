"""Regression tests for vault_write_rename / vault_write_delete's locking —
confirms the get_file_locks(src, dst) refactor didn't change normal,
non-concurrent behavior (see CODE_QUALITY_STANDARDS.md §7: verify after any
meaningful edit)."""

import os

import pytest

from sympose import vault_write_delete, vault_write_rename
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def profile():
    return {"vault_folders": ["*"]}


def test_rename_moves_the_file(vault, profile):
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("hello")
    result = vault_write_rename.rename_note(profile, "A", "B")
    assert result == "Renamed to `B.md`"
    assert not os.path.exists(os.path.join(vault, "A.md"))
    assert os.path.exists(os.path.join(vault, "B.md"))


def test_rename_onto_an_existing_note_is_rejected(vault, profile):
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("a")
    with open(os.path.join(vault, "B.md"), "w") as f:
        f.write("b")
    assert vault_write_rename.rename_note(profile, "A", "B") == NOTE_EXISTS
    # Neither file was touched by the rejected rename.
    assert os.path.exists(os.path.join(vault, "A.md"))
    assert os.path.exists(os.path.join(vault, "B.md"))


def test_rename_missing_note_not_found(vault, profile):
    assert vault_write_rename.rename_note(profile, "Nope", "B") == NOTE_NOT_FOUND


def test_delete_empty_folder_removes_it_outright(vault, profile):
    os.makedirs(os.path.join(vault, "Empty"))
    result = vault_write_delete.delete_folder(profile, "Empty")
    assert "Deleted empty folder" in result
    assert not os.path.exists(os.path.join(vault, "Empty"))


def test_delete_nonempty_folder_moves_to_trash(vault, profile):
    os.makedirs(os.path.join(vault, "Stuff"))
    with open(os.path.join(vault, "Stuff", "note.md"), "w") as f:
        f.write("x")
    result = vault_write_delete.delete_folder(profile, "Stuff")
    assert "Moved folder to the bin" in result
    assert not os.path.exists(os.path.join(vault, "Stuff"))
    assert os.path.exists(os.path.join(vault, ".trash", "Stuff", "note.md"))


def test_delete_folder_resolving_to_vault_root_is_denied(vault, profile):
    assert vault_write_delete.delete_folder(profile, ".") == NOTE_DENIED
    # The vault root itself must survive a rejected delete.
    assert os.path.isdir(vault)


def test_delete_folder_on_trash_itself_is_denied(vault, profile):
    os.makedirs(os.path.join(vault, ".trash"))
    assert vault_write_delete.delete_folder(profile, ".trash") == NOTE_DENIED
    assert os.path.isdir(os.path.join(vault, ".trash"))
