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

from sympose import vault_manifest, vault_write


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


class TestAtomicWrite:
    """D1: write_note/overwrite_note/create_note write via a tmp file +
    os.replace (vault_manifest.write_atomic_text) instead of truncating the
    real file in place - a crash partway through a write must leave any
    pre-existing note untouched rather than truncated, and must still be
    reported back to the caller as an error, not silently swallowed."""

    def test_write_note_failure_leaves_existing_note_untouched(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original content")

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _boom)
        result = vault_write.write_note({"vault_folders": ["*"]}, "Note.md", "new content")

        assert "Error" in result
        assert note_path.read_text() == "original content"

    def test_overwrite_note_failure_leaves_existing_note_untouched(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original content")

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _boom)
        result = vault_write.overwrite_note(
            {"vault_folders": ["*"]}, "Note.md", "new content"
        )

        assert "Error" in result
        assert note_path.read_text() == "original content"

    def test_create_note_failure_reports_error_not_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _boom)
        result = vault_write.create_note(
            {"vault_folders": ["*"]}, "New.md", "hello"
        )

        assert "Error" in result
        assert not (tmp_path / "New.md").exists()

    def test_successful_write_leaves_no_tmp_file_behind(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        vault_write.write_note({"vault_folders": ["*"]}, "Note.md", "hello")
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
        assert leftovers == []

    def test_write_atomic_text_cleans_up_tmp_file_on_failure(
        self, tmp_path, monkeypatch
    ):
        target = tmp_path / "manifest.json"

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _boom)
        try:
            vault_manifest.write_atomic_text(str(target), "{}")
        except OSError:
            pass
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
        assert leftovers == []


class TestOptimisticConcurrencyGuard:
    """ADR-129: write_note/append_note/overwrite_note accept an optional
    expected_mtime and return NOTE_CONFLICT instead of clobbering a file
    that changed since the caller last read it. Default (no expected_mtime)
    behaves exactly as before every one of these tests confirms."""

    def test_overwrite_with_no_expected_mtime_behaves_as_before(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        result = vault_write.overwrite_note({"vault_folders": ["*"]}, "Note.md", "updated")
        assert result.startswith("Saved note:")
        assert note_path.read_text() == "updated\n"

    def test_overwrite_with_matching_expected_mtime_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        mtime = os.stat(note_path).st_mtime
        result = vault_write.overwrite_note(
            {"vault_folders": ["*"]}, "Note.md", "updated", expected_mtime=mtime
        )
        assert result.startswith("Saved note:")
        assert note_path.read_text() == "updated\n"

    def test_overwrite_with_stale_expected_mtime_returns_conflict_and_does_not_write(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        stale_mtime = os.stat(note_path).st_mtime - 999  # definitely not current
        result = vault_write.overwrite_note(
            {"vault_folders": ["*"]}, "Note.md", "updated", expected_mtime=stale_mtime
        )
        assert result == vault_write.NOTE_CONFLICT
        assert note_path.read_text() == "original"

    def test_write_note_with_stale_expected_mtime_returns_conflict(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        result = vault_write.write_note(
            {"vault_folders": ["*"]}, "Note.md", "updated", expected_mtime=12345.0
        )
        assert result == vault_write.NOTE_CONFLICT
        assert note_path.read_text() == "original"

    def test_write_note_expecting_an_existing_file_that_is_gone_returns_conflict(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        mtime = os.stat(note_path).st_mtime
        os.remove(note_path)
        result = vault_write.write_note(
            {"vault_folders": ["*"]}, "Note.md", "new", expected_mtime=mtime
        )
        assert result == vault_write.NOTE_CONFLICT
        assert not note_path.exists()

    def test_append_note_with_stale_expected_mtime_returns_conflict_and_does_not_append(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        result = vault_write.append_note(
            {"vault_folders": ["*"]}, "Note.md", "extra", expected_mtime=12345.0
        )
        assert result == vault_write.NOTE_CONFLICT
        assert note_path.read_text() == "original"

    def test_append_note_with_matching_expected_mtime_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")
        mtime = os.stat(note_path).st_mtime
        result = vault_write.append_note(
            {"vault_folders": ["*"]}, "Note.md", "extra", expected_mtime=mtime
        )
        assert result.startswith("Appended to note:")
        assert note_path.read_text() == "original\nextra\n"

    def test_append_note_still_uses_atomic_replace_not_raw_append_mode(
        self, tmp_path, monkeypatch
    ):
        """D1-style regression for append_note specifically: it used to open
        the target with a raw `open(..., "a")`, bypassing the tmp-file +
        os.replace atomicity every other writer here already gets. A crash
        mid-append must not leave the file half-written."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        note_path = tmp_path / "Note.md"
        _write(str(note_path), "original")

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _boom)
        result = vault_write.append_note({"vault_folders": ["*"]}, "Note.md", "extra")

        assert "Error" in result
        assert note_path.read_text() == "original"


class TestDailyRootBoundaryGuard:
    """Regression: workspace_rules.md says Daily/ is "strictly outside
    persona access boundaries (uses [DAILY_NOTE] system instead)" - that was
    prompt text only, with no code behind it. Asked directly to write there,
    a persona did (confirmed live: a file was actually created in Daily/,
    bypassing write_daily_note's format and tagging entirely)."""

    def test_write_note_refuses_direct_daily_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        result = vault_write.write_note(
            {"vault_folders": ["*"]}, "Daily/test.md", "hello"
        )
        assert "reserved for daily entries" in result
        assert not (tmp_path / "Daily" / "test.md").exists()

    def test_write_note_still_allows_a_normal_folder(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        result = vault_write.write_note(
            {"vault_folders": ["*"]}, "Thoughts/test.md", "hello"
        )
        assert result.startswith("Saved to note:")
        assert (tmp_path / "Thoughts" / "test.md").exists()

    def test_create_note_refuses_direct_daily_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        result = vault_write.create_note(
            {"vault_folders": ["*"]}, "Daily/test2.md", "hello"
        )
        assert result == vault_write.NOTE_DENIED
        assert not (tmp_path / "Daily" / "test2.md").exists()

    def test_guard_follows_a_custom_daily_notes_format_env(
        self, tmp_path, monkeypatch
    ):
        """The guard must read the same root write_daily_note itself would
        use, not a hardcoded "Daily" - otherwise it's just a second place
        for the two to silently drift apart."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setenv("DAILY_NOTES_FORMAT", "Journal/%Y-%m-%d.md")
        blocked = vault_write.write_note(
            {"vault_folders": ["*"]}, "Journal/test.md", "hello"
        )
        assert "reserved for daily entries" in blocked
        allowed = vault_write.write_note(
            {"vault_folders": ["*"]}, "Daily/test.md", "hello"
        )
        assert allowed.startswith("Saved to note:")


class TestTemplateTimeRendering:
    """Regression: {{time}} rendered as a full datetime
    (now.strftime("%Y-%m-%d %H:%M")) instead of time-only. The vault's real
    Thoughts template uses the standard Obsidian `created: {{date}} {{time}}`
    pattern, so this wrote `created: 2026-09-15 2026-09-15 13:47` into every
    new note's frontmatter (confirmed live, both via a real template and via
    the no-template fallback's identical bug)."""

    def test_time_placeholder_is_time_only_via_template(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(
            str(tmp_path / "Templates" / "Thoughts template.md"),
            "---\ntitle: {{title}}\ncreated: {{date}} {{time}}\n---",
        )
        vault_write.write_note({"vault_folders": ["*"]}, "Thoughts/Idea.md", "body")
        content = (tmp_path / "Thoughts" / "Idea.md").read_text()
        created_line = next(
            line for line in content.splitlines() if line.startswith("created:")
        )
        # "YYYY-MM-DD HH:MM" has exactly 2 dashes; a duplicated date has 4.
        assert created_line.count("-") == 2

    def test_time_placeholder_is_time_only_via_fallback(self, tmp_path, monkeypatch):
        """No Templates/ dir at all - the no-template fallback branch has
        its own separate date_str/time_str construction with the identical
        bug, so it needs its own test rather than relying on the template
        path to cover it."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        vault_write.write_note({"vault_folders": ["*"]}, "Thoughts/Idea.md", "body")
        content = (tmp_path / "Thoughts" / "Idea.md").read_text()
        created_line = next(
            line for line in content.splitlines() if line.startswith("created:")
        )
        assert created_line.count("-") == 2


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


class TestRenameNoteCrossFolderCollision:
    """D3: renaming ProjectA/Foo.md must not retarget a bare [[Foo]] link
    that actually meant a different, same-named ProjectB/Foo.md."""

    def _same_stem_finder(self, paths):
        return lambda profile, stem: [
            p for p in paths if os.path.splitext(os.path.basename(p))[0] == stem
        ]

    def test_bare_link_in_unrelated_folder_is_left_alone(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "ProjectA" / "Foo.md"), "content A")
        _write(str(tmp_path / "ProjectB" / "Foo.md"), "content B")
        _write(str(tmp_path / "ProjectB" / "Referrer.md"), "See [[Foo]] for context.")

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "ProjectA/Foo",
            "Bar",
            get_backlinks_fn=lambda profile, stem: [{"rel_path": "ProjectB/Referrer.md"}],
            find_notes_by_stem_fn=self._same_stem_finder(
                ["ProjectA/Foo.md", "ProjectB/Foo.md"]
            ),
        )

        assert "relinked" not in result
        assert (
            tmp_path / "ProjectB" / "Referrer.md"
        ).read_text() == "See [[Foo]] for context."

    def test_bare_link_in_renamed_notes_own_folder_is_still_rewritten(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "ProjectA" / "Foo.md"), "content A")
        _write(str(tmp_path / "ProjectB" / "Foo.md"), "content B")
        _write(
            str(tmp_path / "ProjectA" / "Referrer.md"), "See [[Foo]] for context."
        )

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "ProjectA/Foo",
            "Bar",
            get_backlinks_fn=lambda profile, stem: [{"rel_path": "ProjectA/Referrer.md"}],
            find_notes_by_stem_fn=self._same_stem_finder(
                ["ProjectA/Foo.md", "ProjectB/Foo.md"]
            ),
        )

        assert "1 file relinked" in result
        assert (
            tmp_path / "ProjectA" / "Referrer.md"
        ).read_text() == "See [[Bar]] for context."

    def test_qualified_link_naming_the_other_folder_is_left_alone(
        self, tmp_path, monkeypatch
    ):
        """Even without any ambiguity signal, a link that already names a
        *different* folder than the one being renamed must never be
        rewritten - it's unambiguously not about this note."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "ProjectA" / "Foo.md"), "content A")
        _write(str(tmp_path / "ProjectB" / "Foo.md"), "content B")
        _write(
            str(tmp_path / "Referrer.md"), "See [[ProjectB/Foo]] for context."
        )

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "ProjectA/Foo",
            "Bar",
            get_backlinks_fn=lambda profile, stem: [{"rel_path": "Referrer.md"}],
        )

        assert "relinked" not in result
        assert (tmp_path / "Referrer.md").read_text() == "See [[ProjectB/Foo]] for context."

    def test_qualified_link_naming_the_renamed_notes_folder_is_rewritten(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "ProjectA" / "Foo.md"), "content A")
        _write(
            str(tmp_path / "Referrer.md"), "See [[ProjectA/Foo]] for context."
        )

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "ProjectA/Foo",
            "Bar",
            get_backlinks_fn=lambda profile, stem: [{"rel_path": "Referrer.md"}],
        )

        assert "1 file relinked" in result
        assert (tmp_path / "Referrer.md").read_text() == "See [[ProjectA/Bar]] for context."

    def test_no_ambiguity_when_no_other_note_shares_the_stem(
        self, tmp_path, monkeypatch
    ):
        """The common case: only one note vault-wide has this name, so a
        bare link is unambiguous and rewritten exactly as before."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        _write(str(tmp_path / "ProjectA" / "Foo.md"), "content A")
        _write(
            str(tmp_path / "ProjectB" / "Referrer.md"), "See [[Foo]] for context."
        )

        result = vault_write.rename_note(
            {"vault_folders": ["*"]},
            "ProjectA/Foo",
            "Bar",
            get_backlinks_fn=lambda profile, stem: [{"rel_path": "ProjectB/Referrer.md"}],
            find_notes_by_stem_fn=self._same_stem_finder(["ProjectA/Foo.md"]),
        )

        assert "1 file relinked" in result
        assert (
            tmp_path / "ProjectB" / "Referrer.md"
        ).read_text() == "See [[Bar]] for context."


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
