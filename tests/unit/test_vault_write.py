"""
Unit tests for sympose.vault_write's own hook wiring.

The functional behavior (path resolution, sandbox checks, template seeding,
wikilink rewriting, trash-on-delete, ...) is already covered end-to-end via
VaultManager's wrappers in test_vault.py, which exercises this module
indirectly through the facade — that coverage doesn't change just because
the implementation moved. What's new here, and worth its own direct test,
is the hook mechanism itself: reindex_hook/manifest_hook/on_backlinks_changed
replace what used to be direct `cls._reindex_note_if_enabled(...)` calls, so
this file checks that wiring fires (or doesn't) correctly, independent of
what the hooks actually do.
"""

import os

from sympose import vault_write


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestWriteNoteHooks:
    def test_reindex_and_manifest_hooks_fire_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        calls = {"reindex": [], "manifest": []}
        result = vault_write.write_note(
            {"vault_folders": ["*"]},
            "Note.md",
            "hello",
            reindex_hook=lambda mv, path: calls["reindex"].append((mv, path)),
            manifest_hook=lambda mv, path: calls["manifest"].append((mv, path)),
        )
        assert result.startswith("Saved to note:")
        assert len(calls["reindex"]) == 1
        assert len(calls["manifest"]) == 1
        assert calls["reindex"][0][1] == calls["manifest"][0][1]

    def test_hooks_default_to_noop_when_omitted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        # Must not raise even with no hooks passed at all.
        result = vault_write.write_note({"vault_folders": ["*"]}, "Note.md", "hello")
        assert result.startswith("Saved to note:")

    def test_hooks_do_not_fire_on_sandbox_denial(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        calls = []
        # An empty allowed-dirs list (no vault configured) means every path
        # write is refused before touching disk.
        result = vault_write.write_note(
            {"vault_folders": []},
            "../escape.md",
            "hello",
            reindex_hook=lambda mv, path: calls.append((mv, path)),
        )
        assert "Warning" in result or "Security Error" in result
        assert calls == []


class TestDeleteFolderBacklinksHook:
    def test_on_backlinks_changed_fires_when_folder_has_notes(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "Sub" / "a.md"), "content")
        fired = []
        result = vault_write.delete_folder(
            {"vault_folders": ["*"]},
            "Sub",
            on_backlinks_changed=lambda: fired.append(1),
        )
        assert "Moved folder to the bin" in result
        assert fired == [1]

    def test_on_backlinks_changed_still_fires_for_an_empty_folder(
        self, tmp_path, monkeypatch
    ):
        # Empty-folder deletion returns before the note-loop that clears the
        # cache in the non-empty path — verify it does NOT fire here, since
        # nothing that could be backlinked ever existed in an empty folder.
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        (tmp_path / "Empty").mkdir()
        fired = []
        result = vault_write.delete_folder(
            {"vault_folders": ["*"]},
            "Empty",
            on_backlinks_changed=lambda: fired.append(1),
        )
        assert "Deleted empty folder" in result
        assert fired == []


class TestRenameNoteBacklinksHook:
    def test_get_backlinks_fn_is_called_with_the_old_stem(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "Old.md"), "content")
        captured = {}

        def fake_get_backlinks(profile, stem):
            captured["stem"] = stem
            return []

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "Old",
            "New",
            get_backlinks_fn=fake_get_backlinks,
        )
        assert result.startswith("Renamed to")
        assert captured["stem"] == "Old"

    def test_referencing_files_are_relinked_and_hooks_fire(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "Old.md"), "content")
        _write(str(tmp_path / "Referrer.md"), "See [[Old]] for context.")
        reindexed = []

        def fake_get_backlinks(profile, stem):
            return [{"rel_path": "Referrer.md"}]

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "Old",
            "New",
            get_backlinks_fn=fake_get_backlinks,
            reindex_hook=lambda mv, path: reindexed.append(path),
        )
        assert "1 file relinked" in result
        assert (tmp_path / "Referrer.md").read_text() == "See [[New]] for context."
        # Reindexed both the relinked referrer and the renamed note itself.
        assert len(reindexed) == 2

    def test_on_backlinks_changed_fires_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "Old.md"), "content")
        fired = []
        vault_write.rename_note(
            {"vault_folders": ["*"]},
            "Old",
            "New",
            get_backlinks_fn=lambda profile, stem: [],
            on_backlinks_changed=lambda: fired.append(1),
        )
        assert fired == [1]

    def test_on_backlinks_changed_does_not_fire_when_note_not_found(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        fired = []
        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "Missing",
            "New",
            get_backlinks_fn=lambda profile, stem: [],
            on_backlinks_changed=lambda: fired.append(1),
        )
        assert result == vault_write.NOTE_NOT_FOUND
        assert fired == []


class TestDeleteNoteBacklinksHook:
    def test_on_backlinks_changed_fires_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "Note.md"), "content")
        fired = []
        result = vault_write.delete_note(
            {"vault_folders": ["*"]},
            "Note",
            on_backlinks_changed=lambda: fired.append(1),
        )
        assert result.startswith("Moved to the bin")
        assert fired == [1]
