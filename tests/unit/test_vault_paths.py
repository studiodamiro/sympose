"""
Unit tests for sympose.vault_paths — vault root & sandbox path resolution.
"""

import os
import time

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


# ---------------------------------------------------------------------------
# D6: dirs_mtime must catch an in-place content edit to an existing note, not
# just an add/remove/rename - a directory's own mtime never moves for the
# former, only the latter.
# ---------------------------------------------------------------------------


class TestDirsMtime:
    def test_empty_dirs_list_returns_zero(self):
        assert vault_paths.dirs_mtime([]) == 0.0

    def test_reflects_a_new_file_being_added(self, tmp_path):
        before = vault_paths.dirs_mtime([str(tmp_path)])
        (tmp_path / "new.md").write_text("hello")
        after = vault_paths.dirs_mtime([str(tmp_path)])
        assert after > before

    def test_in_place_edit_to_existing_file_moves_the_watermark(self, tmp_path):
        """The actual D6 bug: editing an existing note's content changes the
        file's own mtime but never its parent directory's - a watermark
        built from directory mtimes alone would miss this indefinitely,
        serving a stale cache/index/manifest forever until some unrelated
        add/remove/rename happened to touch a watched directory."""
        note = tmp_path / "note.md"
        note.write_text("original")
        dir_mtime_before = os.stat(tmp_path).st_mtime
        before = vault_paths.dirs_mtime([str(tmp_path)])

        # os.utime on an EXISTING file never touches its parent directory's
        # mtime - only adding/removing/renaming an entry does. This isolates
        # "the file's own mtime moved" from any directory-level side effect.
        future = time.time() + 100
        os.utime(note, (future, future))
        assert os.stat(tmp_path).st_mtime == dir_mtime_before

        after = vault_paths.dirs_mtime([str(tmp_path)])
        assert after > before

    def test_nested_file_edit_is_seen_without_requiring_the_subfolder_listed(
        self, tmp_path
    ):
        """Not just the top-level directory - dirs_mtime walks the whole
        tree, so a note several folders deep is covered by passing just the
        vault root, the normal call shape."""
        nested = tmp_path / "Projects" / "Sympose"
        nested.mkdir(parents=True)
        note = nested / "note.md"
        note.write_text("original")
        before = vault_paths.dirs_mtime([str(tmp_path)])

        future = time.time() + 100
        os.utime(note, (future, future))
        after = vault_paths.dirs_mtime([str(tmp_path)])
        assert after > before

    def test_ignored_subfolder_is_not_walked(self, tmp_path):
        ignored = tmp_path / "Attachments"
        ignored.mkdir()
        note = ignored / "image-note.md"
        note.write_text("noise")
        before = vault_paths.dirs_mtime([str(tmp_path)], {"attachments"})

        future = time.time() + 100
        os.utime(note, (future, future))
        after = vault_paths.dirs_mtime([str(tmp_path)], {"attachments"})
        assert after == before
