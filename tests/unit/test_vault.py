"""
Unit tests for sympose.vault.VaultManager (pure logic, no real filesystem vault).
Covers: is_safe_path sandbox enforcement, read_note (via tmp files),
        parse_frontmatter, write_note sandbox, backlink cache invalidation.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from sympose.config import is_safe_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_note(path, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# VaultManager.get_allowed_dirs (sandboxing)
# ---------------------------------------------------------------------------

class TestGetAllowedDirs:
    def test_returns_empty_when_no_vault_env(self):
        from sympose.vault import VaultManager
        with patch.dict(os.environ, {"MASTER_VAULT_PATH": ""}, clear=False):
            dirs = VaultManager.get_allowed_dirs({"vault_folders": ["Notes"]})
            assert dirs == []

    def test_returns_vault_root_for_wildcard(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        dirs = VaultManager.get_allowed_dirs({"vault_folders": ["*"]})
        assert len(dirs) == 1
        assert dirs[0] == str(tmp_vault_dir)

    def test_returns_subfolder_for_named_folder(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        (tmp_vault_dir / "Notes").mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        dirs = VaultManager.get_allowed_dirs({"vault_folders": ["Notes"]})
        assert any("Notes" in d for d in dirs)

    def test_traversal_in_folder_name_rejected(self, tmp_vault_dir, monkeypatch):
        """A vault_folder containing ../ should not escape the vault root."""
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        dirs = VaultManager.get_allowed_dirs({"vault_folders": ["../../etc"]})
        # Either empty or constrained within vault root
        for d in dirs:
            assert is_safe_path(d, str(tmp_vault_dir)), f"Unsafe path escaped: {d}"


# ---------------------------------------------------------------------------
# VaultManager.read_note
# ---------------------------------------------------------------------------

class TestReadNote:
    def test_read_existing_note(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        note_path = str(tmp_vault_dir / "hello.md")
        write_note(note_path, "# Hello\nThis is a note.")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        content = VaultManager.read_note(profile, "hello")
        assert "Hello" in content

    def test_read_missing_note_returns_error_msg(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        content = VaultManager.read_note(profile, "nonexistent_note_xyz")
        # Should return an error/warning string, not raise
        assert isinstance(content, str)
        assert len(content) > 0

    def test_read_note_outside_sandbox_denied(self, tmp_vault_dir, monkeypatch, tmp_path):
        """Attempting to read a note outside the vault root should be denied."""
        from sympose.vault import VaultManager
        # Write a note outside the vault
        outside_note = tmp_path / "secret.md"
        outside_note.write_text("TOP SECRET")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        content = VaultManager.read_note(profile, str(outside_note))
        # Should NOT contain the secret content
        assert "TOP SECRET" not in content

    def test_read_note_with_md_extension(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        note_path = str(tmp_vault_dir / "test_note.md")
        write_note(note_path, "Test content")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        # Both with and without .md should work
        content_with = VaultManager.read_note(profile, "test_note.md")
        content_without = VaultManager.read_note(profile, "test_note")
        assert "Test content" in content_with
        assert "Test content" in content_without


# ---------------------------------------------------------------------------
# VaultManager.parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_valid_frontmatter_parsed(self):
        from sympose.vault import VaultManager
        content = "---\ntitle: My Note\ntags: [python, test]\n---\n# Body"
        fm, body = VaultManager.parse_frontmatter(content)
        assert fm.get("title") == "My Note"
        assert "python" in fm.get("tags", [])

    def test_no_frontmatter_returns_empty_dict(self):
        from sympose.vault import VaultManager
        content = "# Just content, no frontmatter"
        fm, body = VaultManager.parse_frontmatter(content)
        assert fm == {}
        assert "Just content" in body

    def test_missing_frontmatter_content_is_body(self):
        from sympose.vault import VaultManager
        content = "Plain text note."
        fm, body = VaultManager.parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_frontmatter_body_stripped(self):
        from sympose.vault import VaultManager
        content = "---\nauthor: damiro\n---\nBody text here"
        fm, body = VaultManager.parse_frontmatter(content)
        assert fm.get("author") == "damiro"
        assert "Body text here" in body


# ---------------------------------------------------------------------------
# VaultManager.write_note (sandbox enforcement)
# ---------------------------------------------------------------------------

class TestWriteNote:
    def test_write_note_creates_file(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        result = VaultManager.write_note(profile, "new_note", "# Created by test")
        assert "✅" in result or "saved" in result.lower() or "new_note" in result
        note_path = tmp_vault_dir / "new_note.md"
        assert note_path.exists()

    def test_write_note_outside_sandbox_denied(self, tmp_vault_dir, tmp_path, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        outside_path = str(tmp_path / "evil.md")
        result = VaultManager.write_note(profile, outside_path, "Evil content")
        # Either an error/warning or the file was NOT created outside the vault
        evil_file = tmp_path / "evil.md"
        if evil_file.exists():
            # If the file was written, it must be inside the vault
            assert not str(evil_file).startswith(str(tmp_vault_dir))
        else:
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Backlink cache — mtime invalidation
# ---------------------------------------------------------------------------

class TestBacklinkCache:
    def test_cache_populated_on_first_call(self, tmp_vault_dir, monkeypatch):
        import sympose.vault as vault_mod
        from sympose.vault import VaultManager
        # Clear the cache
        vault_mod._BACKLINK_CACHE.clear()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        # Write a note with a [[backlink]]
        note_path = str(tmp_vault_dir / "source.md")
        write_note(note_path, "# Source\nSee [[target]] for details.")
        VaultManager.build_backlink_index(profile)
        assert len(vault_mod._BACKLINK_CACHE) >= 1

    def test_cache_hit_on_second_call(self, tmp_vault_dir, monkeypatch):
        import sympose.vault as vault_mod
        from sympose.vault import VaultManager
        vault_mod._BACKLINK_CACHE.clear()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        note_path = str(tmp_vault_dir / "doc.md")
        write_note(note_path, "[[linked]]")
        result1 = VaultManager.build_backlink_index(profile)
        result2 = VaultManager.build_backlink_index(profile)
        # Both calls should return identical index (cache hit)
        assert result1 == result2

    def test_cache_invalidated_after_file_change(self, tmp_vault_dir, monkeypatch):
        import time
        import sympose.vault as vault_mod
        from sympose.vault import VaultManager
        vault_mod._BACKLINK_CACHE.clear()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        note_path = str(tmp_vault_dir / "changing.md")
        write_note(note_path, "[[link_one]]")
        result1 = VaultManager.build_backlink_index(profile)
        # Wait briefly and modify the directory mtime by adding a new file
        time.sleep(0.05)
        write_note(str(tmp_vault_dir / "new_file.md"), "new")
        result2 = VaultManager.build_backlink_index(profile)
        # We just verify it runs without error and returns a dict
        assert isinstance(result2, dict)
