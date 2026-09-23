"""Tests for sympose.server_search_handlers — fail-closed persona resolution
via require_profile (docs/decisions/009)."""

import pytest
from fastapi import HTTPException

from sympose import server_search_handlers as sh


def test_search_vault_404s_an_unknown_persona_with_a_profiles_dir_configured(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "samantha.yaml").write_text("name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    with pytest.raises(HTTPException) as exc_info:
        sh.search_vault("anything", "some-typo-handle")
    assert exc_info.value.status_code == 404
