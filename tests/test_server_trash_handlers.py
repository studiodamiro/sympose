"""Tests for sympose.server_trash_handlers — fail-closed persona resolution
via require_profile (docs/decisions/009)."""

from helpers import write_persona
import pytest
from fastapi import HTTPException

from sympose import server_trash_handlers as th
from sympose.server_models import TrashEmpty, TrashRestore


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return profiles


def test_list_trash_404s_an_unknown_persona_with_a_profiles_dir_configured(profiles_dir):
    with pytest.raises(HTTPException) as exc_info:
        th.list_trash("some-typo-handle")
    assert exc_info.value.status_code == 404


def test_every_mutating_trash_handler_404s_an_unknown_persona(profiles_dir):
    """`_require_trash_scope` (restore/purge/empty) now routes through
    `require_profile` the same way `_trash_scope` (list) does -- confirms
    all three, not just the read route already covered above."""
    calls = [
        lambda: th.restore_trash(TrashRestore(path="X.md", persona="bogus")),
        lambda: th.purge_trash("X.md", "bogus"),
        lambda: th.empty_trash(TrashEmpty(persona="bogus")),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
