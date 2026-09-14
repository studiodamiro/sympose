"""
Unit tests for sympose.vault_paths — vault root & sandbox path resolution.
"""

from sympose import vault_paths


class TestGetMasterVault:
    def test_none_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("MASTER_VAULT_PATH", raising=False)
        assert vault_paths.get_master_vault() is None

    def test_expands_user_and_resolves_absolute(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        assert vault_paths.get_master_vault() == str(tmp_path)


class TestGetVaultName:
    def test_none_when_no_vault(self, monkeypatch):
        monkeypatch.delenv("MASTER_VAULT_PATH", raising=False)
        assert vault_paths.get_vault_name() is None

    def test_returns_root_basename(self, monkeypatch, tmp_path):
        vault_root = tmp_path / "MyVault"
        vault_root.mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(vault_root))
        assert vault_paths.get_vault_name() == "MyVault"


class TestGetAllowedDirs:
    def test_returns_empty_when_no_vault_env(self, monkeypatch):
        monkeypatch.delenv("MASTER_VAULT_PATH", raising=False)
        assert vault_paths.get_allowed_dirs({"vault_folders": ["Notes"]}) == []

    def test_wildcard_returns_vault_root(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        dirs = vault_paths.get_allowed_dirs({"vault_folders": ["*"]})
        assert dirs == [str(tmp_path)]

    def test_empty_string_folder_also_means_unrestricted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        assert vault_paths.get_allowed_dirs({"vault_folders": [""]}) == [str(tmp_path)]

    def test_named_folder_is_created_and_returned(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        dirs = vault_paths.get_allowed_dirs({"vault_folders": ["Notes"]})
        assert dirs == [str(tmp_path / "Notes")]
        assert (tmp_path / "Notes").is_dir()

    def test_legacy_singular_vault_folder_key_still_works(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        dirs = vault_paths.get_allowed_dirs({"vault_folder": "Journal"})
        assert dirs == [str(tmp_path / "Journal")]

    def test_traversal_in_folder_name_cannot_escape_the_vault(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        dirs = vault_paths.get_allowed_dirs({"vault_folders": ["../../etc"]})
        for d in dirs:
            assert str(tmp_path) in d

    def test_falls_back_to_vault_root_when_nothing_resolves_safely(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        dirs = vault_paths.get_allowed_dirs({"vault_folders": ["../../etc"]})
        assert dirs == [str(tmp_path)]


class TestGetPrimaryDir:
    def test_none_when_no_allowed_dirs(self, monkeypatch):
        monkeypatch.delenv("MASTER_VAULT_PATH", raising=False)
        assert vault_paths.get_primary_dir({"vault_folders": ["Notes"]}) is None

    def test_returns_first_allowed_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        assert vault_paths.get_primary_dir({"vault_folders": ["Notes"]}) == str(
            tmp_path / "Notes"
        )
