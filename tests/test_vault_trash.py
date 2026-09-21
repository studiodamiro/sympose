"""Tests for vault_trash.py — list/restore/purge of the trash-recovery
surface, including the clash-index round-trip and the locking added this
session."""

import os

import pytest

from sympose import vault_trash
from sympose.vault_trash_index import record_clash
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path):
    return str(tmp_path)


@pytest.fixture
def allowed(vault):
    return [vault]


def _trash(vault, rel_path, content="x"):
    """Puts a file straight into `.trash/<rel_path>`, as if `delete_note`
    had already moved it there."""
    dest = os.path.join(vault, vault_trash.TRASH_DIRNAME, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write(content)
    return dest


def test_list_trashed_empty_when_no_trash_dir(vault, allowed):
    assert vault_trash.list_trashed(vault, allowed) == []


def test_list_trashed_returns_items_newest_first(vault, allowed):
    _trash(vault, "A.md")
    a_path = os.path.join(vault, vault_trash.TRASH_DIRNAME, "A.md")
    os.utime(a_path, (1000, 1000))
    _trash(vault, "B.md")
    b_path = os.path.join(vault, vault_trash.TRASH_DIRNAME, "B.md")
    os.utime(b_path, (2000, 2000))

    rows = vault_trash.list_trashed(vault, allowed)
    assert [r["trash_path"] for r in rows] == ["B.md", "A.md"]
    assert rows[0]["original_path"] == "B.md"


def test_list_trashed_omits_entries_outside_allowed_dirs(vault):
    _trash(vault, "Scoped/A.md")
    # allowed_dirs is a different, unrelated subfolder — the original
    # location ("Scoped/A.md") resolves outside it.
    other_dir = os.path.join(vault, "Other")
    os.makedirs(other_dir)
    assert vault_trash.list_trashed(vault, [other_dir]) == []


def test_restore_moves_the_file_back(vault, allowed):
    _trash(vault, "A.md", "hello")
    result = vault_trash.restore(vault, allowed, "A.md")
    assert result == "A.md"
    assert os.path.exists(os.path.join(vault, "A.md"))
    assert not os.path.exists(os.path.join(vault, ".trash", "A.md"))


def test_restore_missing_entry_not_found(vault, allowed):
    assert vault_trash.restore(vault, allowed, "Nope.md") == NOTE_NOT_FOUND


def test_restore_rejects_path_outside_trash_root(vault, allowed):
    assert vault_trash.restore(vault, allowed, "../../etc/passwd") == NOTE_DENIED


def test_restore_onto_an_occupied_destination_is_rejected(vault, allowed):
    _trash(vault, "A.md")
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("already here")
    assert vault_trash.restore(vault, allowed, "A.md") == NOTE_EXISTS
    # Both copies survive a rejected restore.
    assert os.path.exists(os.path.join(vault, ".trash", "A.md"))
    assert os.path.exists(os.path.join(vault, "A.md"))


def test_restore_honors_the_clash_index(vault, allowed):
    # Simulates what delete_note does on a same-named clash: the trashed
    # file gets a timestamp-suffixed name, and the index records what its
    # real original path was.
    _trash(vault, "A-20260101000000.md")
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    record_clash(troot, "A-20260101000000.md", "Notes/A.md")

    result = vault_trash.restore(vault, allowed, "A-20260101000000.md")
    assert result == "Notes/A.md"
    assert os.path.exists(os.path.join(vault, "Notes", "A.md"))


def test_purge_deletes_permanently(vault, allowed):
    _trash(vault, "A.md")
    assert vault_trash.purge(vault, allowed, "A.md") == ""
    assert not os.path.exists(os.path.join(vault, ".trash", "A.md"))


def test_purge_missing_entry_not_found(vault, allowed):
    assert vault_trash.purge(vault, allowed, "Nope.md") == NOTE_NOT_FOUND


def test_purge_all_removes_every_in_scope_entry(vault, allowed):
    _trash(vault, "A.md")
    _trash(vault, "B.md")
    assert vault_trash.purge_all(vault, allowed) == 2
    assert vault_trash.list_trashed(vault, allowed) == []
