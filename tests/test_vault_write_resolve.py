"""Resolving an existing note: a bare name may be looked up by name, an exact path only as itself.

Also a regression test for a `/code-review` finding: `_resolve_note_recursively` used to return
whichever same-stem note the filesystem happened to enumerate first, with no tie-break —
filesystem-order-dependent, not deterministic. Fixed to resolve to the alphabetically-first path."""

import os

import pytest
from fastapi import HTTPException

from sympose import server_handlers, vault_write, vault_write_delete, vault_write_rename, vault_write_resolve
from sympose.vault_write_status import NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def profile():
    return {"vault_folders": ["*"]}


def test_resolve_bare_name_at_allowed_dir_top_level(vault, profile):
    with open(os.path.join(vault, "Solo.md"), "w") as f:
        f.write("x")
    resolved = vault_write_resolve.resolve_existing_note(profile, "Solo")
    assert resolved == os.path.join(vault, "Solo.md")


def test_resolve_ambiguous_stem_is_deterministic(vault, profile):
    """Two notes sharing a stem in different folders, neither at an
    allowed dir's own top level (so resolution falls through to the
    recursive case) -- must always resolve to the same, alphabetically-
    first path regardless of filesystem enumeration order."""
    zeta_path = os.path.join(vault, "Zeta", "Nested")
    os.makedirs(zeta_path)
    with open(os.path.join(zeta_path, "Ideas.md"), "w") as f:
        f.write("zeta")
    alpha_path = os.path.join(vault, "Alpha", "Nested")
    os.makedirs(alpha_path)
    with open(os.path.join(alpha_path, "Ideas.md"), "w") as f:
        f.write("alpha")

    resolved = vault_write_resolve.resolve_existing_note(profile, "Ideas")
    assert resolved == os.path.join(alpha_path, "Ideas.md")

    # Deterministic across repeated calls, not just lucky once.
    for _ in range(5):
        assert vault_write_resolve.resolve_existing_note(profile, "Ideas") == os.path.join(
            alpha_path, "Ideas.md"
        )


# --- an exact path resolves only as that path ------------------------------------------------


def write_note(vault, rel, text="body"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


@pytest.mark.parametrize("name", ["A/Note.md", "A/Note", "Missing/Deeper/Note.md"])
def test_an_exact_path_that_does_not_exist_does_not_resolve_to_a_note_of_the_same_name(vault, profile, name):
    write_note(vault, "B/Note.md")
    assert vault_write_resolve.resolve_existing_note(profile, name) is None


def test_an_exact_path_resolves_to_that_note_even_when_another_has_the_same_name(vault, profile):
    write_note(vault, "A/Note.md", "a")
    write_note(vault, "B/Note.md", "b")
    assert vault_write_resolve.resolve_existing_note(profile, "B/Note") == os.path.join(vault, "B", "Note.md")


def test_a_bare_name_still_finds_the_note_in_a_folder(vault, profile):
    path = write_note(vault, "Deep/Er/Note.md")
    assert vault_write_resolve.resolve_existing_note(profile, "Note") == path
    assert vault_write_resolve.resolve_existing_note(profile, "note.md") == path


@pytest.mark.xfail(
    strict=True,
    reason="the tree lists .markdown and .txt files as notes, but the resolver always appends .md, "
    "so the web app cannot open, save, rename or delete them",
)
@pytest.mark.parametrize("name", ["F/a.txt", "F/b.markdown"])
def test_an_exact_path_to_a_note_with_another_note_extension_resolves(vault, profile, name):
    path = write_note(vault, name)
    assert vault_write_resolve.resolve_existing_note(profile, name) == path


# The four callers: with only `B/Note.md` present, a request for `A/Note.md` (a tree that is out of
# date, a double click) must be "not found" and leave `B/Note.md` alone.


@pytest.fixture
def only_b(vault):
    return write_note(vault, "B/Note.md", "keep me")


def unchanged(path):
    with open(path, encoding="utf-8") as f:
        return f.read() == "keep me"


def test_reading_an_exact_path_that_is_gone_is_not_found(only_b):
    with pytest.raises(HTTPException) as exc_info:
        server_handlers.read_note("A/Note.md", None)
    assert exc_info.value.status_code == 404


def test_saving_an_exact_path_that_is_gone_is_not_found_and_overwrites_nothing(only_b, profile):
    assert vault_write.overwrite_note(profile, "A/Note.md", "clobbered") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_renaming_an_exact_path_that_is_gone_is_not_found_and_moves_nothing(only_b, profile):
    assert vault_write_rename.rename_note(profile, "A/Note.md", "Other") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_deleting_an_exact_path_that_is_gone_is_not_found_and_trashes_nothing(only_b, profile):
    assert vault_write_delete.delete_note(profile, "A/Note.md") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_an_exact_path_does_not_fall_back_to_a_note_of_that_name_at_the_top_of_the_vault(vault, profile):
    write_note(vault, "Note.md")
    assert vault_write_resolve.resolve_existing_note(profile, "A/Note.md") is None


def test_an_exact_path_to_a_folder_is_not_a_note(vault, profile):
    os.makedirs(os.path.join(vault, "A", "Folder.md"))
    assert vault_write_resolve.resolve_existing_note(profile, "A/Folder.md") is None


def test_a_bare_name_prefers_the_note_at_the_top_of_an_allowed_folder_to_a_deeper_one(vault):
    top = write_note(vault, "Code/Note.md")
    write_note(vault, "Code/Aa/Note.md")  # sorts first, so only the top-level rule can pick `top`
    restricted = {"vault_folders": ["Code"]}
    assert vault_write_resolve.resolve_existing_note(restricted, "Note") == top


@pytest.mark.parametrize("ghost", [".trash/Ghost.md", ".hidden/Ghost.md", "Attachments/Ghost.md"])
def test_a_bare_name_does_not_find_a_note_in_the_bin_or_a_hidden_or_ignored_folder(vault, profile, ghost):
    write_note(vault, ghost)
    assert vault_write_resolve.resolve_existing_note(profile, "Ghost") is None


@pytest.mark.parametrize("link", ["Link.md", "Deep/Er/Link.md"])
def test_a_note_that_is_a_link_to_a_file_outside_the_vault_does_not_resolve(vault, profile, tmp_path_factory, link):
    outside = tmp_path_factory.mktemp("outside") / "secret.md"
    outside.write_text("secret")
    os.makedirs(os.path.dirname(os.path.join(vault, link)), exist_ok=True)
    os.symlink(outside, os.path.join(vault, link))
    assert vault_write_resolve.resolve_existing_note(profile, "Link") is None
