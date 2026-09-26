"""Where a renamed note ends up: a bare name stays in the note's folder, `Folder/name` is relative
to the vault, and a leading slash (`/name`) is the vault root. The route reports the real new path."""

import os

import pytest

from sympose import server_handlers, vault_write_rename
from sympose.server_models import NoteRename
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

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


def exists(vault, rel):
    return os.path.isfile(os.path.join(vault, rel))


def test_a_bare_new_name_keeps_the_note_in_its_folder(vault):
    write(vault, "F/a.md")
    assert vault_write_rename.rename_note(ALL, "F/a.md", "b") == "Renamed to `F/b.md`"
    assert exists(vault, "F/b.md") and not exists(vault, "F/a.md") and not exists(vault, "b.md")


def test_a_new_name_with_a_folder_is_relative_to_the_vault(vault):
    write(vault, "F/a.md")
    assert vault_write_rename.rename_note(ALL, "F/a.md", "G/H/b") == "Renamed to `G/H/b.md`"
    assert exists(vault, "G/H/b.md") and not exists(vault, "F/a.md")


@pytest.mark.parametrize("new_name", ["/a", "/a.md", "'/a'", "\\a"])
def test_a_leading_slash_moves_the_note_to_the_vault_root(vault, new_name):
    write(vault, "F/a.md", "text")
    assert vault_write_rename.rename_note(ALL, "F/a.md", new_name) == "Renamed to `a.md`"
    assert exists(vault, "a.md") and not exists(vault, "F/a.md")
    with open(os.path.join(vault, "a.md"), encoding="utf-8") as f:
        assert f.read() == "text"


def test_a_leading_slash_keeps_a_folder_relative_to_the_vault(vault):
    write(vault, "F/a.md")
    assert vault_write_rename.rename_note(ALL, "F/a.md", "/G/b") == "Renamed to `G/b.md`"


def test_moving_to_the_root_onto_a_note_already_there_is_rejected(vault):
    write(vault, "F/a.md", "in folder")
    write(vault, "a.md", "at root")
    assert vault_write_rename.rename_note(ALL, "F/a.md", "/a") == NOTE_EXISTS
    assert exists(vault, "F/a.md")


def test_a_restricted_persona_cannot_move_a_note_to_the_root_outside_its_folders(vault):
    write(vault, "Code/a.md")
    assert vault_write_rename.rename_note({"vault_folders": ["Code"]}, "Code/a.md", "/a") == NOTE_DENIED
    assert exists(vault, "Code/a.md") and not exists(vault, "a.md")


def test_a_slash_alone_is_not_a_name(vault):
    write(vault, "F/a.md")
    assert vault_write_rename.rename_note(ALL, "F/a.md", "/") == NOTE_DENIED
    assert exists(vault, "F/a.md")


def test_a_note_that_lands_on_the_destination_after_the_first_check_is_not_overwritten(vault):
    write(vault, "a.md", "mine")

    def another_request_creates_the_target(_profile, _stem):
        write(vault, "b.md", "someone else's note")  # after the early check, before the rename's lock
        return []

    result = vault_write_rename.rename_note(
        ALL, "a", "b", get_backlinks_fn=another_request_creates_the_target, find_notes_by_stem_fn=lambda *_: []
    )
    assert result == NOTE_EXISTS
    with open(os.path.join(vault, "b.md"), encoding="utf-8") as f:
        assert f.read() == "someone else's note"
    assert exists(vault, "a.md")


# --- the route ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "reported"),
    [("F/a.md", "b", "F/b.md"), ("F/a.md", "/a", "a.md"), ("F/a.md", "G/b", "G/b.md"), ("F/a.md", "b.md", "F/b.md")],
)
def test_the_route_reports_the_notes_real_new_path(vault, old, new, reported):
    write(vault, old)
    result = server_handlers.rename_note(NoteRename(path=old, new_path=new))
    assert result["path"] == reported
    assert exists(vault, reported)
