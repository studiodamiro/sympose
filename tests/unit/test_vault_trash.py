"""
Unit tests for the `<vault>/.trash` recovery surface (ADR-085):
`sympose.vault_trash` free functions and the `VaultManager` wrappers
(`list_trash` / `restore_from_trash` / `purge_from_trash` / `empty_trash`),
plus the defensive trash-target guard added to `delete_note`.
"""

import os

from sympose import vault_trash


def write_note(path, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _trash(vault, rel, content="junk"):
    """Drop a file straight into `<vault>/.trash/<rel>` as `delete_note` would."""
    write_note(str(vault / ".trash" / rel), content)


# ---------------------------------------------------------------------------
# vault_trash._original_relpath — clash-suffix stripping
# ---------------------------------------------------------------------------

class TestOriginalRelpath:
    def test_plain_path_unchanged(self):
        assert vault_trash._original_relpath("Notes/idea.md") == "Notes/idea.md"

    def test_strips_delete_note_timestamp_suffix(self):
        assert (
            vault_trash._original_relpath("Notes/idea-20260910120000.md")
            == "Notes/idea.md"
        )

    def test_leaves_other_trailing_digits_alone(self):
        assert vault_trash._original_relpath("Notes/part-2.md") == "Notes/part-2.md"


# ---------------------------------------------------------------------------
# VaultManager.list_trash
# ---------------------------------------------------------------------------

class TestListTrash:
    def test_lists_trashed_notes_newest_first(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        _trash(tmp_vault_dir, "Notes/old.md")
        _trash(tmp_vault_dir, "scrap.md")
        older = tmp_vault_dir / ".trash" / "Notes" / "old.md"
        os.utime(older, (1_000_000, 1_000_000))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        items = VaultManager.list_trash({"vault_folders": ["*"]})

        assert [i["original_path"] for i in items] == ["scrap.md", "Notes/old.md"]
        assert items[0]["trash_path"] == "scrap.md"
        assert items[0]["size"] > 0

    def test_empty_when_no_trash_dir(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        assert VaultManager.list_trash({"vault_folders": ["*"]}) == []

    def test_scoped_out_entries_are_hidden(self, tmp_vault_dir, monkeypatch):
        """A trashed note whose original folder is outside the persona's
        allowed folders must not appear in that persona's listing."""
        from sympose.vault import VaultManager
        (tmp_vault_dir / "Private").mkdir()
        (tmp_vault_dir / "Shared").mkdir()
        _trash(tmp_vault_dir, "Private/secret.md")
        _trash(tmp_vault_dir, "Shared/note.md")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        items = VaultManager.list_trash({"vault_folders": ["Shared"]})

        assert [i["original_path"] for i in items] == ["Shared/note.md"]


# ---------------------------------------------------------------------------
# VaultManager.restore_from_trash
# ---------------------------------------------------------------------------

class TestRestoreFromTrash:
    def test_round_trips_to_original_path(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        _trash(tmp_vault_dir, "Notes/reborn.md", "# Reborn\n")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.restore_from_trash(
            {"vault_folders": ["*"]}, "Notes/reborn.md"
        )

        assert result == "Restored to `Notes/reborn.md`"
        assert (tmp_vault_dir / "Notes" / "reborn.md").read_text() == "# Reborn\n"
        assert not (tmp_vault_dir / ".trash" / "Notes").exists()  # empty dir pruned

    def test_strips_clash_suffix_on_restore(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        _trash(tmp_vault_dir, "dupe-20260910120000.md", "recovered")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.restore_from_trash(
            {"vault_folders": ["*"]}, "dupe-20260910120000.md"
        )

        assert result == "Restored to `dupe.md`"
        assert (tmp_vault_dir / "dupe.md").read_text() == "recovered"

    def test_missing_entry_not_found(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.restore_from_trash({"vault_folders": ["*"]}, "ghost.md")
        assert result == VaultManager.NOTE_NOT_FOUND

    def test_original_path_occupied_refused(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        write_note(str(tmp_vault_dir / "here.md"), "live copy")
        _trash(tmp_vault_dir, "here.md", "trashed copy")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.restore_from_trash({"vault_folders": ["*"]}, "here.md")

        assert result == VaultManager.NOTE_EXISTS
        assert (tmp_vault_dir / "here.md").read_text() == "live copy"
        assert (tmp_vault_dir / ".trash" / "here.md").read_text() == "trashed copy"

    def test_traversal_in_trash_path_denied(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        write_note(str(tmp_vault_dir.parent / "outside.md"), "x")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.restore_from_trash(
            {"vault_folders": ["*"]}, "../../outside.md"
        )
        assert result in (VaultManager.NOTE_DENIED, VaultManager.NOTE_NOT_FOUND)

    def test_restore_out_of_scope_denied(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        (tmp_vault_dir / "Private").mkdir()
        _trash(tmp_vault_dir, "Private/secret.md", "s")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.restore_from_trash(
            {"vault_folders": ["Shared"]}, "Private/secret.md"
        )

        assert result == VaultManager.NOTE_DENIED
        assert (tmp_vault_dir / ".trash" / "Private" / "secret.md").exists()


# ---------------------------------------------------------------------------
# VaultManager.purge_from_trash / empty_trash
# ---------------------------------------------------------------------------

class TestPurge:
    def test_purge_removes_the_file(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        _trash(tmp_vault_dir, "Notes/gone.md")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.purge_from_trash({"vault_folders": ["*"]}, "Notes/gone.md")

        assert result == "Deleted permanently"
        assert not (tmp_vault_dir / ".trash" / "Notes" / "gone.md").exists()
        assert not (tmp_vault_dir / ".trash" / "Notes").exists()  # pruned

    def test_purge_missing_not_found(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.purge_from_trash({"vault_folders": ["*"]}, "ghost.md")
        assert result == VaultManager.NOTE_NOT_FOUND

    def test_empty_trash_clears_only_in_scope(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        (tmp_vault_dir / "Private").mkdir()
        (tmp_vault_dir / "Shared").mkdir()
        _trash(tmp_vault_dir, "Shared/a.md")
        _trash(tmp_vault_dir, "Shared/b.md")
        _trash(tmp_vault_dir, "Private/keep.md")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.empty_trash({"vault_folders": ["Shared"]})

        assert result == "Emptied trash (2 notes)"
        assert not (tmp_vault_dir / ".trash" / "Shared").exists()
        assert (tmp_vault_dir / ".trash" / "Private" / "keep.md").exists()


# ---------------------------------------------------------------------------
# delete_note — defensive trash-target guard (ADR-085 hardening)
# ---------------------------------------------------------------------------

class TestDeleteNoteTrashGuard:
    def test_rejects_trash_target_escaping_the_vault(self, tmp_path, monkeypatch):
        """If an allowed folder sits far enough above the vault root that the
        preserved relative path would send the `.trash` copy outside the vault,
        `delete_note` refuses rather than writing outside `mv`."""
        from sympose.vault import VaultManager
        mv = tmp_path / "a" / "b"
        mv.mkdir(parents=True)
        write_note(str(tmp_path / "loot.md"), "secret")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(mv))
        monkeypatch.setattr(
            VaultManager, "get_allowed_dirs",
            classmethod(lambda cls, profile: [str(tmp_path)]),
        )

        result = VaultManager.delete_note({"vault_folders": ["*"]}, "loot")

        assert result == VaultManager.NOTE_DENIED
        assert (tmp_path / "loot.md").read_text() == "secret"
