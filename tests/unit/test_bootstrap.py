"""
Unit tests for sympose.bootstrap — the fresh-workspace starter templates and
first-run onboarding.

Covers a real regression: SAMANTHA_YAML (the persona template every fresh
`pipx install` actually writes to disk) used to hardcode
vault_folders: ["General", "Projects", "Thoughts", "Templates"] — folders
that get auto-created inside whatever vault a new user links, and outside of
which Samantha has zero visibility. That contradicts the "adapts to any
folder taxonomy" claim for the one persona guaranteed to ship. Fixed to
vault_folders: ["*"] (full vault access, nothing auto-created).
"""

import os
import yaml
import pytest

from sympose.bootstrap import SAMANTHA_YAML, ensure_workspace
from sympose.vault import VaultManager


class TestSamanthaTemplate:
    def test_parses_as_valid_yaml(self):
        data = yaml.safe_load(SAMANTHA_YAML)
        assert data["handle"] == "samantha"

    def test_vault_folders_is_full_access_wildcard(self):
        """The regression: a fixed folder list isn't taxonomy-agnostic and
        auto-creates folders inside a new user's real vault."""
        data = yaml.safe_load(SAMANTHA_YAML)
        assert data["vault_folders"] == ["*"]

    def test_full_access_creates_no_folders_in_a_pre_existing_vault(self, tmp_path, monkeypatch):
        """get_allowed_dirs on a wildcard profile must not os.makedirs anything
        — a fixed-folder-list profile would create each listed folder."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "MyOwnStructure").mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(vault))

        data = yaml.safe_load(SAMANTHA_YAML)
        dirs = VaultManager.get_allowed_dirs(data)

        assert dirs == [str(vault)]
        assert os.listdir(vault) == ["MyOwnStructure"], "wildcard access must not create any new folders"


class TestEnsureWorkspace:
    def test_fresh_workspace_writes_samantha_with_full_vault_access(self, tmp_path):
        ws = str(tmp_path / "ws")
        is_fresh = ensure_workspace(ws)
        assert is_fresh is True

        with open(os.path.join(ws, "profiles", "samantha.yaml"), encoding="utf-8") as f:
            data = yaml.safe_load(f.read())
        assert data["vault_folders"] == ["*"]

    def test_existing_workspace_is_not_overwritten(self, tmp_path):
        ws = str(tmp_path / "ws")
        ensure_workspace(ws)
        sam_file = os.path.join(ws, "profiles", "samantha.yaml")
        with open(sam_file, "a", encoding="utf-8") as f:
            f.write("\n# user customization marker\n")

        is_fresh_second_call = ensure_workspace(ws)
        assert is_fresh_second_call is False
        with open(sam_file, encoding="utf-8") as f:
            assert "user customization marker" in f.read()
