"""Regression test for a `/code-review` finding: read_note's except OSError
turned a concurrent delete (racing in between resolve_existing_note
returning a path and open() reaching it) into a 500, since
FileNotFoundError is also an OSError -- fixed to return 404 for that
specific case instead."""

import os

import pytest
from fastapi import HTTPException

from sympose import server_handlers


def test_read_note_race_deleted_between_resolve_and_open_returns_404(monkeypatch, tmp_path):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    note = tmp_path / "Note.md"
    note.write_text("hello")
    real_target = str(note)

    def racing_resolve(profile, path):
        # Simulates a concurrent delete landing between path resolution
        # and open(): the path is real when resolved, gone by the time
        # read_note tries to open it.
        os.remove(real_target)
        return real_target

    monkeypatch.setattr(server_handlers, "resolve_existing_note", racing_resolve)

    with pytest.raises(HTTPException) as exc_info:
        server_handlers.read_note("Note.md", None)
    assert exc_info.value.status_code == 404


def test_read_note_returns_content_and_mtime(monkeypatch, tmp_path):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    (tmp_path / "Note.md").write_text("hello\n")

    result = server_handlers.read_note("Note.md", None)
    assert result["path"] == "Note.md"
    assert result["content"] == "hello"
    assert result["mtime"] > 0


def test_require_profile_404s_an_unknown_persona_with_a_profiles_dir_configured(
    monkeypatch, tmp_path
):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "samantha.yaml").write_text("name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    with pytest.raises(HTTPException) as exc_info:
        server_handlers.require_profile("some-typo-handle")
    assert exc_info.value.status_code == 404


def test_require_profile_error_names_the_default_handle_not_none(monkeypatch, tmp_path):
    """Regression test (`/code-review` finding): an omitted persona
    (None) that fails to resolve used to report "Unknown persona
    `None`." -- useless for debugging which persona actually broke.
    Uses a configured custom default with no matching file, since the
    factory default ("samantha") has its own whole-vault safety net and
    would never actually reach the 404 path here."""
    from sympose import settings_store

    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    profiles = tmp_path / "profiles"
    profiles.mkdir()  # exists but has no dev.yaml -- configured default fails to resolve
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    settings_store.set("default_persona", "dev")

    with pytest.raises(HTTPException) as exc_info:
        server_handlers.require_profile(None)
    assert "dev" in exc_info.value.detail
    assert "None" not in exc_info.value.detail


def test_unknown_persona_cannot_read_outside_a_scoped_profiles_folders(monkeypatch, tmp_path):
    """Regression test for the live-verified sandbox bypass: before the
    profile.py fix, an unknown/typo'd persona with a profiles dir
    configured silently got whole-vault access instead of being
    rejected. Proves this is closed end-to-end through the real route
    handlers, not just that get_profile returns None in isolation."""
    vault = tmp_path / "vault"
    (vault / "Code").mkdir(parents=True)
    (vault / "Code" / "Note.md").write_text("in scope")
    (vault / "Secret").mkdir()
    (vault / "Secret" / "secret.md").write_text("should never be readable")
    monkeypatch.setenv("VAULT_PATHS", str(vault))

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "dev.yaml").write_text("name: Dev\nvault_folders:\n  - Code\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    with pytest.raises(HTTPException) as exc_info:
        server_handlers.get_vault_tree("bogus-handle")
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        server_handlers.read_note("Secret/secret.md", "bogus-handle")
    assert exc_info.value.status_code == 404


def test_note_write_body_defaults_persona_to_none_and_still_resolves(monkeypatch, tmp_path):
    """`NoteWrite.persona` (and its siblings) changed from a hardcoded
    `"samantha"` literal default to `None` -- confirms omitting the field
    entirely still round-trips through `require_profile`'s None-means-
    "use the configured default persona" handling, not just that passing
    an explicit handle string works."""
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    (tmp_path / "Note.md").write_text("original\n")

    body = server_handlers.NoteWrite(path="Note.md", content="updated")
    assert body.persona is None

    result = server_handlers.write_note(body)
    assert result["path"] == "Note.md"
    assert (tmp_path / "Note.md").read_text() == "updated\n"


def test_every_persona_scoped_handler_404s_an_unknown_persona(monkeypatch, tmp_path):
    """require_profile replaced a bare resolve_profile call in all 8
    handlers here, not just the 3 (get_vault_tree/read_note/write_note)
    already covered above -- confirms the other 5 (create_note,
    create_folder, rename_note, delete_note, delete_folder) actually got
    the same wiring, not just a visual copy-paste that missed one."""
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "samantha.yaml").write_text("name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    calls = [
        lambda: server_handlers.create_note(
            server_handlers.NoteCreate(path="X.md", persona="bogus")
        ),
        lambda: server_handlers.create_folder(
            server_handlers.FolderCreate(path="X", persona="bogus")
        ),
        lambda: server_handlers.rename_note(
            server_handlers.NoteRename(path="X.md", new_path="Y.md", persona="bogus")
        ),
        lambda: server_handlers.delete_note("X.md", "bogus"),
        lambda: server_handlers.delete_folder("X", "bogus"),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
