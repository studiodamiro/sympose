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
# vault_trash._original_relpath — clash-suffix resolution via the sidecar
# index (D4: no longer inferred by stripping a trailing `-\d{14}`, which
# false-positived on a legitimately timestamp-named file).
# ---------------------------------------------------------------------------


class TestOriginalRelpath:
    def test_no_index_entry_returns_path_unchanged(self, tmp_path):
        assert (
            vault_trash._original_relpath(str(tmp_path), "Notes/idea.md")
            == "Notes/idea.md"
        )

    def test_naturally_timestamp_suffixed_name_is_not_stripped(self, tmp_path):
        """D4's actual false positive: with no index entry recorded, a name
        that merely *looks* like it carries a disambiguating suffix (but
        never went through a real clash) is left exactly as-is."""
        assert (
            vault_trash._original_relpath(
                str(tmp_path), "Notes/idea-20260910120000.md"
            )
            == "Notes/idea-20260910120000.md"
        )

    def test_recorded_clash_resolves_via_index(self, tmp_path):
        troot = str(tmp_path)
        vault_trash.record_clash(
            troot, "Notes/idea-20260910120000.md", "Notes/idea.md"
        )
        assert (
            vault_trash._original_relpath(troot, "Notes/idea-20260910120000.md")
            == "Notes/idea.md"
        )


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

    def test_naturally_timestamp_named_file_restores_to_itself(
        self, tmp_vault_dir, monkeypatch
    ):
        """D4: a file sitting in trash that was never actually involved in a
        clash (dropped straight in, the way a real one predating this fix
        might be) restores to its own name unchanged, not a name-minus-
        suffix guess."""
        from sympose.vault import VaultManager

        _trash(tmp_vault_dir, "dupe-20260910120000.md", "recovered")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.restore_from_trash(
            {"vault_folders": ["*"]}, "dupe-20260910120000.md"
        )

        assert result == "Restored to `dupe-20260910120000.md`"
        assert (tmp_vault_dir / "dupe-20260910120000.md").read_text() == "recovered"

    def test_real_clash_restores_second_copy_to_its_true_original_path(
        self, tmp_vault_dir, monkeypatch
    ):
        """End-to-end through delete_note: two notes deleted at the same
        vault-relative path clash in the trash, so the second gets a
        timestamp suffix. Restoring that suffixed entry must land back at
        the real original path (D4) - recorded explicitly at delete time,
        not inferred from the filename afterward."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        write_note(str(tmp_vault_dir / "dupe.md"), "first version")
        VaultManager.delete_note(profile, "dupe.md")

        write_note(str(tmp_vault_dir / "dupe.md"), "second version")
        VaultManager.delete_note(profile, "dupe.md")

        rows = VaultManager.list_trash(profile)
        assert {r["original_path"] for r in rows} == {"dupe.md"}
        suffixed = next(r for r in rows if r["trash_path"] != "dupe.md")

        result = VaultManager.restore_from_trash(profile, suffixed["trash_path"])

        assert result == "Restored to `dupe.md`"
        assert (tmp_vault_dir / "dupe.md").read_text() == "second version"

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

        result = VaultManager.purge_from_trash(
            {"vault_folders": ["*"]}, "Notes/gone.md"
        )

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

        assert result == "Emptied the bin (2 notes)"
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
        from sympose import vault_paths
        from sympose.vault import VaultManager

        mv = tmp_path / "a" / "b"
        mv.mkdir(parents=True)
        write_note(str(tmp_path / "loot.md"), "secret")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(mv))
        # delete_note's real logic now lives in vault_write.py, which resolves
        # allowed dirs via vault_paths directly (not through VaultManager) —
        # patch the actual call site rather than the VaultManager facade.
        monkeypatch.setattr(
            vault_paths, "get_allowed_dirs", lambda profile: [str(tmp_path)]
        )

        result = VaultManager.delete_note({"vault_folders": ["*"]}, "loot")

        assert result == VaultManager.NOTE_DENIED
        assert (tmp_path / "loot.md").read_text() == "secret"
