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
