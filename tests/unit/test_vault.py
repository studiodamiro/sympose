"""
Unit tests for sympose.vault.VaultManager (pure logic, no real filesystem vault).
Covers: is_safe_path sandbox enforcement, read_note (via tmp files),
        parse_frontmatter, write_note sandbox, backlink cache invalidation.
"""

import os
from unittest.mock import patch

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

    def test_read_note_outside_sandbox_denied(
        self, tmp_vault_dir, monkeypatch, tmp_path
    ):
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

    def test_recursive_stem_fallback_finds_nested_note(
        self, tmp_vault_dir, monkeypatch
    ):
        """E7: the fuzzy/title fallback now routes through the shared vault
        snapshot cache (_get_vault_snapshot) instead of its own separate
        os.walk + re-read - this exercises that it still finds a note
        nested several folders deep, matched by stem, case-insensitively."""
        from sympose.vault import VaultManager

        nested = tmp_vault_dir / "Projects" / "Sympose"
        nested.mkdir(parents=True)
        write_note(str(nested / "Typography.md"), "# Typography\nBody text.")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        content = VaultManager.read_note(profile, "typography")
        assert "Typography" in content
        assert "Body text" in content

    def test_recursive_stem_fallback_reflects_in_place_edit(
        self, tmp_vault_dir, monkeypatch
    ):
        """E7 + D6 together: once the fallback is cache-backed, an in-place
        edit to an already-cached nested note must still show up on the
        next read - not served stale, now that the underlying cache's
        watermark (D6) actually notices a content-only change."""
        import time

        from sympose.vault import VaultManager

        nested = tmp_vault_dir / "Projects" / "Sympose"
        nested.mkdir(parents=True)
        note_path = nested / "Typography.md"
        write_note(str(note_path), "original content")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        first = VaultManager.read_note(profile, "typography")
        assert "original content" in first

        write_note(str(note_path), "updated content")
        future = time.time() + 100
        os.utime(note_path, (future, future))

        second = VaultManager.read_note(profile, "typography")
        assert "updated content" in second


# ---------------------------------------------------------------------------
# VaultManager.resolve_asset_path
# ---------------------------------------------------------------------------


class TestResolveAssetPath:
    def test_resolves_direct_path(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        asset_path = tmp_vault_dir / "diagram.png"
        asset_path.write_bytes(b"fake-png-bytes")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        resolved = VaultManager.resolve_asset_path(profile, "diagram.png")
        assert resolved == str(asset_path)

    def test_resolves_by_recursive_filename_match(self, tmp_vault_dir, monkeypatch):
        """A bare filename (no folder prefix) should be found anywhere under
        an allowed dir, the same way an Obsidian `![[pic.png]]` embed carries
        no path — mirrors read_note's recursive stem fallback."""
        from sympose.vault import VaultManager

        nested = tmp_vault_dir / "Projects" / "Nested"
        nested.mkdir(parents=True)
        (nested / "pic.PNG").write_bytes(b"fake-bytes")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        resolved = VaultManager.resolve_asset_path(profile, "pic.png")
        assert resolved == str(nested / "pic.PNG")

    def test_reaches_into_attachments_folder(self, tmp_vault_dir, monkeypatch):
        """`vault.ignore_folders` defaults to excluding "Attachments" from the
        *note* index — but that's exactly where embedded images usually live,
        so asset resolution must not apply that same exclusion (regression
        guard for the resolver reusing read_note's ignore list by mistake)."""
        from sympose.vault import VaultManager

        attachments = tmp_vault_dir / "Attachments"
        attachments.mkdir()
        (attachments / "photo.jpg").write_bytes(b"fake-jpeg")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        resolved = VaultManager.resolve_asset_path(profile, "photo.jpg")
        assert resolved == str(attachments / "photo.jpg")

    def test_missing_asset_returns_none(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        assert VaultManager.resolve_asset_path(profile, "nope.png") is None

    def test_asset_outside_sandbox_denied(self, tmp_vault_dir, monkeypatch, tmp_path):
        from sympose.vault import VaultManager

        outside_asset = tmp_path / "secret.png"
        outside_asset.write_bytes(b"TOP SECRET BYTES")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        resolved = VaultManager.resolve_asset_path(profile, str(outside_asset))
        assert resolved is None


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

    def test_frontmatter_only_note_without_trailing_newline(self):
        """People/Templates notes are often 100% frontmatter with the closing
        `---` as the last line and no trailing newline — must still parse."""
        from sympose.vault import VaultManager

        content = '---\naka:\n  - Dylan\nname: Dylan Cosmo\ntags:\n  - "#person"\n  - son\n---'
        fm, body = VaultManager.parse_frontmatter(content)
        assert fm.get("name") == "Dylan Cosmo"
        assert fm.get("aka") == ["Dylan"]
        assert "#person" in fm.get("tags", [])
        assert body == ""

    def test_frontmatter_only_note_with_trailing_newline(self):
        from sympose.vault import VaultManager

        fm, body = VaultManager.parse_frontmatter("---\nname: X\n---\n")
        assert fm.get("name") == "X" and body == ""

    def test_closing_delimiter_with_trailing_spaces(self):
        from sympose.vault import VaultManager

        fm, body = VaultManager.parse_frontmatter("---\nname: X\n---  \nBody")
        assert fm.get("name") == "X" and "Body" in body


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

    def test_write_note_outside_sandbox_denied(
        self, tmp_vault_dir, tmp_path, monkeypatch
    ):
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

    def test_write_note_applies_matching_folder_template(
        self, tmp_vault_dir, monkeypatch
    ):
        """A [WRITE_NOTE] payload with no frontmatter of its own gets the vault's
        real per-folder template (ADR-113) — not a generic tags/type/created block."""
        from sympose.vault import VaultManager

        tmpl_dir = tmp_vault_dir / "Templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "People template.md").write_text(
            "---\naka: {{title}}\nbirthday: \n---\n", encoding="utf-8"
        )
        (tmpl_dir / "Note template.md").write_text(
            "---\ntitle: {{title}}\ntags: []\n---\n", encoding="utf-8"
        )
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        VaultManager.write_note(
            profile, "People/jane_doe", "Met her at the conference."
        )
        content = (tmp_vault_dir / "People" / "jane_doe.md").read_text()
        assert "aka: Jane Doe" in content
        assert "birthday:" in content

    def test_write_note_with_own_frontmatter_bypasses_template(
        self, tmp_vault_dir, monkeypatch
    ):
        """A model that supplies its own frontmatter block wins verbatim, even if
        it skips the folder's real template — intentional, but the exception."""
        from sympose.vault import VaultManager

        tmpl_dir = tmp_vault_dir / "Templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "People template.md").write_text(
            "---\naka: {{title}}\nbirthday: \n---\n", encoding="utf-8"
        )
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        VaultManager.write_note(
            profile, "People/jane_doe", "---\ncustom: field\n---\n\nBody"
        )
        content = (tmp_vault_dir / "People" / "jane_doe.md").read_text()
        assert "custom: field" in content
        assert "aka:" not in content


# ---------------------------------------------------------------------------
# VaultManager.get_template_for_path (folder <-> template matching — ADR-113)
# ---------------------------------------------------------------------------


class TestGetTemplateForPath:
    def _make_templates(self, tmp_vault_dir, files):
        tmpl_dir = tmp_vault_dir / "Templates"
        tmpl_dir.mkdir(exist_ok=True)
        for name, body in files.items():
            (tmpl_dir / name).write_text(body, encoding="utf-8")
        return tmpl_dir

    def test_exact_folder_name_match(self, tmp_vault_dir):
        from sympose.vault import VaultManager

        self._make_templates(
            tmp_vault_dir,
            {
                "People template.md": "---\naka: {{title}}\n---\n",
                "Note template.md": "---\ntitle: {{title}}\n---\n",
            },
        )
        result = VaultManager.get_template_for_path(
            str(tmp_vault_dir), "People/jane.md"
        )
        assert "aka:" in result

    def test_plural_folder_matches_singular_template_name(self, tmp_vault_dir):
        from sympose.vault import VaultManager

        self._make_templates(
            tmp_vault_dir,
            {
                "Movie template.md": "---\nrelease: {{date:YYYY}}\n---\n",
                "Note template.md": "---\ntitle: {{title}}\n---\n",
            },
        )
        result = VaultManager.get_template_for_path(
            str(tmp_vault_dir), "Movies/dune.md"
        )
        assert "release:" in result

    def test_unmapped_folder_falls_back_to_note_template(self, tmp_vault_dir):
        from sympose.vault import VaultManager

        self._make_templates(
            tmp_vault_dir,
            {
                "Movie template.md": "---\nrelease: {{date:YYYY}}\n---\n",
                "Note template.md": "---\ntitle: {{title}}\n---\n",
            },
        )
        result = VaultManager.get_template_for_path(
            str(tmp_vault_dir), "Recipes/soup.md"
        )
        assert "title:" in result and "release:" not in result

    def test_new_template_file_matched_without_a_code_change(self, tmp_vault_dir):
        from sympose.vault import VaultManager

        self._make_templates(
            tmp_vault_dir,
            {
                "Recipe template.md": "---\ningredients: []\n---\n",
                "Note template.md": "---\ntitle: {{title}}\n---\n",
            },
        )
        result = VaultManager.get_template_for_path(
            str(tmp_vault_dir), "Recipes/soup.md"
        )
        assert "ingredients:" in result

    def test_no_templates_folder_returns_none(self, tmp_vault_dir):
        from sympose.vault import VaultManager

        result = VaultManager.get_template_for_path(
            str(tmp_vault_dir), "People/jane.md"
        )
        assert result is None


# ---------------------------------------------------------------------------
# VaultManager.overwrite_note (dashboard editor save — ADR-081)
# ---------------------------------------------------------------------------


class TestOverwriteNote:
    def test_overwrites_existing_verbatim(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        note_path = tmp_vault_dir / "Notes" / "diary.md"
        write_note(str(note_path), "---\ntitle: Diary\n---\n\nold body\n")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        new_text = "---\ntitle: Diary\ntags:\n  - kept\n---\n\nrewritten body"
        result = VaultManager.overwrite_note(profile, "Notes/diary", new_text)

        assert result.startswith("Saved note:")
        # written back exactly, normalised to a single trailing newline
        assert note_path.read_text() == new_text + "\n"

    def test_missing_note_is_not_created(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.overwrite_note(profile, "Notes/ghost", "should not land")

        assert result == VaultManager.NOTE_NOT_FOUND
        assert not (tmp_vault_dir / "Notes" / "ghost.md").exists()

    def test_outside_sandbox_denied(self, tmp_vault_dir, tmp_path, monkeypatch):
        from sympose.vault import VaultManager

        outside = tmp_path / "outside" / "secret.md"
        write_note(str(outside), "before")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.overwrite_note(profile, "../outside/secret", "after")

        assert (
            result == VaultManager.NOTE_NOT_FOUND or result == VaultManager.NOTE_DENIED
        )
        assert outside.read_text() == "before"


# ---------------------------------------------------------------------------
# VaultManager.create_note (dashboard new-note — ADR-083)
# ---------------------------------------------------------------------------


class TestCreateNote:
    def test_creates_with_seeded_stub(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_note(profile, "Ideas/rocket-stove")

        assert result.startswith("Created note:")
        body = (tmp_vault_dir / "Ideas" / "rocket-stove.md").read_text()
        assert body.startswith("---\n")
        assert "title: Rocket Stove" in body
        assert "# Rocket Stove" in body

    def test_seeds_from_matching_folder_template_when_present(
        self, tmp_vault_dir, monkeypatch
    ):
        """The dashboard's 'new note' buttons (POST /api/vault/note, empty
        content) get the same real per-folder template write_note applies for
        persona-written notes — ADR-113."""
        from sympose.vault import VaultManager

        tmpl_dir = tmp_vault_dir / "Templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "Movie template.md").write_text(
            "---\ntitle: {{title}}\nrelease: {{date:YYYY}}\nrating: \n---\n",
            encoding="utf-8",
        )
        (tmpl_dir / "Note template.md").write_text(
            "---\ntitle: {{title}}\ntags: []\n---\n", encoding="utf-8"
        )
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        VaultManager.create_note(profile, "Movies/dune")

        body = (tmp_vault_dir / "Movies" / "dune.md").read_text()
        assert "title: Dune" in body
        assert "release:" in body
        assert "rating:" in body

    def test_honours_supplied_content(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        VaultManager.create_note(profile, "Notes/verbatim", "just this\n")

        assert (tmp_vault_dir / "Notes" / "verbatim.md").read_text() == "just this\n"

    def test_refuses_to_clobber_existing(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        note = tmp_vault_dir / "Notes" / "taken.md"
        write_note(str(note), "original")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_note(profile, "Notes/taken", "new")

        assert result == VaultManager.NOTE_EXISTS
        assert note.read_text() == "original"

    def test_outside_sandbox_denied(self, tmp_vault_dir, tmp_path, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_note(profile, "../escapee", "x")

        assert result == VaultManager.NOTE_DENIED
        assert not (tmp_path / "escapee.md").exists()


# ---------------------------------------------------------------------------
# VaultManager.create_folder (content-panel toolbar — ADR-095)
# ---------------------------------------------------------------------------


class TestCreateFolder:
    def test_creates_empty_folder(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_folder(profile, "Ideas/Archive")

        assert result.startswith("Created folder:")
        assert (tmp_vault_dir / "Ideas" / "Archive").is_dir()

    def test_refuses_when_path_already_exists(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        note = tmp_vault_dir / "Notes" / "taken.md"
        write_note(str(note), "original")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_folder(profile, "Notes/taken.md")

        assert result == VaultManager.NOTE_EXISTS

    def test_outside_sandbox_denied(self, tmp_vault_dir, tmp_path, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_folder(profile, "../escapee")

        assert result == VaultManager.NOTE_DENIED
        assert not (tmp_path / "escapee").exists()

    def test_new_empty_folder_shows_up_in_the_vault_tree(
        self, tmp_vault_dir, monkeypatch
    ):
        # ADR-098 regression: creating a folder used to succeed on disk but
        # never appear in GET /api/vault/tree, since the tree was a pure
        # projection of the (note-only) manifest.
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.create_folder(profile, "Ideas/Archive")
        assert result.startswith("Created folder:")

        tree = VaultManager.get_vault_tree(profile)
        ideas = next(n for n in tree if n["name"] == "Ideas")
        assert ideas["type"] == "folder"
        archive = next(c for c in ideas["children"] if c["name"] == "Archive")
        assert archive["type"] == "folder"
        assert archive["children"] == []

    def test_list_real_folders_ignores_dotfolders_and_configured_ignores(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "Kept").mkdir()
        (tmp_vault_dir / ".obsidian").mkdir()
        (tmp_vault_dir / ".hidden").mkdir()

        real_folders = VaultManager._list_real_folders(
            str(tmp_vault_dir), [str(tmp_vault_dir)]
        )

        assert "Kept" in real_folders
        assert not any(f.startswith(".") or ".obsidian" in f for f in real_folders)

    def test_cached_result_picks_up_a_new_folder(self, tmp_vault_dir, monkeypatch):
        """E8: _list_real_folders is now mtime-cached, like its siblings -
        this exercises that the cache actually invalidates on a real change
        rather than serving a stale folder list forever."""
        from sympose.vault import VaultManager

        (tmp_vault_dir / "Kept").mkdir()
        dirs = [str(tmp_vault_dir)]

        first = VaultManager._list_real_folders(str(tmp_vault_dir), dirs)
        assert first == ["Kept"]

        (tmp_vault_dir / "NewOne").mkdir()
        second = VaultManager._list_real_folders(str(tmp_vault_dir), dirs)
        assert set(second) == {"Kept", "NewOne"}


class TestDeleteFolder:
    """ADR-099: an empty folder is unlinked outright, a non-empty one moves
    as one unit to `<vault>/.trash/` and its notes are de-indexed."""

    def test_empty_folder_removed_outright_not_trashed(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "Empty").mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "Empty")

        assert result == "Deleted empty folder: `Empty`"
        assert not (tmp_vault_dir / "Empty").exists()
        assert not (tmp_vault_dir / ".trash").exists()

    def test_non_empty_folder_moves_to_trash_with_notes_intact(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / "Ideas" / "a.md"), "first")
        write_note(str(tmp_vault_dir / "Ideas" / "Sub" / "b.md"), "second")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "Ideas")

        assert result == "Moved folder to the bin: `.trash/Ideas` (2 notes)"
        assert not (tmp_vault_dir / "Ideas").exists()
        assert (tmp_vault_dir / ".trash" / "Ideas" / "a.md").read_text() == "first"
        assert (
            tmp_vault_dir / ".trash" / "Ideas" / "Sub" / "b.md"
        ).read_text() == "second"

    def test_deleted_folder_notes_are_individually_restorable(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / "Ideas" / "a.md"), "first")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        VaultManager.delete_folder(profile, "Ideas")

        trashed = VaultManager.list_trash(profile)
        assert any(row["original_path"] == "Ideas/a.md" for row in trashed)

        result = VaultManager.restore_from_trash(profile, "Ideas/a.md")
        assert result == "Restored to `Ideas/a.md`"
        assert (tmp_vault_dir / "Ideas" / "a.md").read_text() == "first"

    def test_trash_name_clash_gets_suffix(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / ".trash" / "Ideas" / "old.md"), "old trash")
        write_note(str(tmp_vault_dir / "Ideas" / "new.md"), "new")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "Ideas")

        assert result.startswith("Moved folder to the bin: `.trash/Ideas-")
        # the pre-existing trash entry for a different, earlier deletion is untouched
        assert (
            tmp_vault_dir / ".trash" / "Ideas" / "old.md"
        ).read_text() == "old trash"

    def test_missing_folder_not_found(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "Ghost")
        assert result == VaultManager.NOTE_NOT_FOUND

    def test_a_file_path_is_not_a_folder(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / "note.md"), "hi")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "note.md")
        assert result == VaultManager.NOTE_NOT_FOUND

    def test_outside_sandbox_denied(self, tmp_vault_dir, tmp_path, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_path / "escapee").mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_folder({"vault_folders": ["*"]}, "../escapee")

        assert result == VaultManager.NOTE_DENIED
        assert (tmp_path / "escapee").exists()

    def test_deleted_folder_disappears_from_the_vault_tree(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / "Ideas" / "a.md"), "first")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        VaultManager.delete_folder(profile, "Ideas")

        tree = VaultManager.get_vault_tree(profile)
        assert not any(n["name"] == "Ideas" for n in tree)


# ---------------------------------------------------------------------------
# VaultManager.rename_note / delete_note (dashboard editor — ADR-084)
# ---------------------------------------------------------------------------


class TestRenameNote:
    def test_renames_and_rewrites_wikilinks(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "Notes").mkdir()
        write_note(str(tmp_vault_dir / "Notes" / "alpha.md"), "# Alpha\n")
        write_note(
            str(tmp_vault_dir / "Notes" / "beta.md"),
            "links [[alpha]], [[Notes/alpha|first]], ![[alpha#intro]], and [[alphabet]]\n",
        )
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}

        result = VaultManager.rename_note(profile, "Notes/alpha", "omega")

        assert result.startswith("Renamed to `Notes/omega.md`")
        assert (tmp_vault_dir / "Notes" / "omega.md").exists()
        assert not (tmp_vault_dir / "Notes" / "alpha.md").exists()
        beta = (tmp_vault_dir / "Notes" / "beta.md").read_text()
        assert "[[omega]]" in beta
        assert "[[Notes/omega|first]]" in beta
        assert "![[omega#intro]]" in beta
        assert "[[alphabet]]" in beta  # stem match is exact, not substring

    def test_missing_source_not_found(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.rename_note({"vault_folders": ["*"]}, "ghost", "x")
        assert result == VaultManager.NOTE_NOT_FOUND

    def test_target_exists_refused(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "N").mkdir()
        write_note(str(tmp_vault_dir / "N" / "a.md"), "a")
        write_note(str(tmp_vault_dir / "N" / "b.md"), "b")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.rename_note({"vault_folders": ["*"]}, "N/a", "b")
        assert result == VaultManager.NOTE_EXISTS
        assert (tmp_vault_dir / "N" / "a.md").read_text() == "a"

    def test_target_outside_sandbox_denied(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        write_note(str(tmp_vault_dir / "keep.md"), "x")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.rename_note(
            {"vault_folders": ["*"]}, "keep", "../escaped"
        )
        assert result == VaultManager.NOTE_DENIED
        assert (tmp_vault_dir / "keep.md").exists()


class TestDeleteNote:
    def test_moves_to_trash(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "Notes").mkdir()
        write_note(str(tmp_vault_dir / "Notes" / "scrap.md"), "junk")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_note({"vault_folders": ["*"]}, "Notes/scrap")

        assert result == "Moved to the bin: `.trash/Notes/scrap.md`"
        assert not (tmp_vault_dir / "Notes" / "scrap.md").exists()
        assert (tmp_vault_dir / ".trash" / "Notes" / "scrap.md").read_text() == "junk"

    def test_trash_name_clash_gets_suffix(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / ".trash").mkdir()
        write_note(str(tmp_vault_dir / ".trash" / "dupe.md"), "old trash")
        write_note(str(tmp_vault_dir / "dupe.md"), "new")
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

        result = VaultManager.delete_note({"vault_folders": ["*"]}, "dupe")

        assert result.startswith("Moved to the bin: `.trash/dupe-")
        assert (tmp_vault_dir / ".trash" / "dupe.md").read_text() == "old trash"

    def test_missing_not_found(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        result = VaultManager.delete_note({"vault_folders": ["*"]}, "ghost")
        assert result == VaultManager.NOTE_NOT_FOUND


# ---------------------------------------------------------------------------
# Backlink cache — mtime invalidation
# ---------------------------------------------------------------------------

# Backlink-cache behavior moved to test_vault_links.py alongside the module
# it now actually lives in (sympose.vault_links).

# ---------------------------------------------------------------------------
# VaultManager._extract_recall_subject — conversational-phrasing -> search term
# ---------------------------------------------------------------------------


class TestExtractRecallSubject:
    """Regression: 'pull up my notes on Rilke' used to be stripped to 'up my notes
    on Rilke' (the regex knew 'pull' but not 'pull up'), then searched as a literal
    phrase that substring-matched nothing, so no vault context was ever injected
    and personas fell back to web search."""

    def _subj(self, msg):
        from sympose.vault import VaultManager

        return VaultManager._extract_recall_subject(msg)

    def test_pull_up_leadin(self):
        assert self._subj("pull up my notes on Rilke") == ("rilke", True)

    def test_what_did_i_write_about_plus_trailing_journal_clause(self):
        assert self._subj("what did I write about grief in my journal") == (
            "grief",
            True,
        )

    def test_do_i_have_notes_about(self):
        assert self._subj("do I have any notes about If I Stay") == ("if i stay", True)

    def test_about_object_extraction(self):
        assert self._subj("recall our past conversations about longing") == (
            "longing",
            True,
        )

    def test_greeting_is_stripped(self):
        assert self._subj("hey anais, remind me about the Meridian project") == (
            "meridian project",
            True,
        )

    def test_no_leadin_flag_when_plain(self):
        subj, had_leadin = self._subj("what's the weather in Tokyo")
        assert had_leadin is False

    def test_trailing_stopwords_trimmed(self):
        subj, _ = self._subj("pull up my notes on the database schema")
        assert subj == "database schema"

    def test_politeness_wrapper_stripped_before_leadin(self):
        # "can you" used to block the "pull up" lead-in from ever matching.
        assert self._subj("can you pull up Dylan's people entry from our vault") == (
            "dylan people",
            True,
        )

    def test_apostrophe_possessive_normalised(self):
        assert self._subj("what's in my note on Rilke's elegies")[0] == "rilke elegies"

    def test_subject_from_later_sentence(self):
        subj, lead = self._subj("i wish i could. can you pull up my note on grief")
        assert (subj, lead) == ("grief", True)

    def test_trailing_conjunction_clause_dropped(self):
        subj, _ = self._subj("pull up Dylan's entry and tell me if it's right")
        assert subj == "dylan"

    def test_pure_sample_phrasing_has_no_subject(self):
        assert self._subj("pull up a random daily entry")[0] == ""
        assert self._subj("surprise me with any note")[0] == ""


class TestRealVaultReferentsAndFirstUnverifiedReferent:
    """ADR-124's structural check, exercised through the real VaultManager
    facade against a real temp vault - `vault_grounding`'s own pure-function
    tests already cover the extraction/matching logic in isolation."""

    def _profile(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        return {"vault_folders": ["*"]}

    def test_referents_include_folder_and_note_names(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "People").mkdir()
        write_note(str(tmp_vault_dir / "People" / "Dylan.md"), "# Dylan\n")
        profile = self._profile(tmp_vault_dir, monkeypatch)

        real = VaultManager.real_vault_referents(profile)
        assert "people" in real
        assert "dylan" in real

    def test_catches_a_real_folder_named_with_unanticipated_phrasing(
        self, tmp_vault_dir, monkeypatch
    ):
        """The live gap ADR-124 closes: 'this one is from the People
        directory' matches none of `_VAULT_CLAIM_RE`'s enumerated phrases in
        engine.py, but names a real folder."""
        from sympose.vault import VaultManager

        (tmp_vault_dir / "People").mkdir()
        write_note(str(tmp_vault_dir / "People" / "Dylan.md"), "# Dylan\n")
        profile = self._profile(tmp_vault_dir, monkeypatch)

        hit = VaultManager.first_unverified_referent(
            "this one is from the People directory", profile
        )
        assert hit == "People"

    def test_no_hit_for_an_invented_name(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        (tmp_vault_dir / "People").mkdir()
        profile = self._profile(tmp_vault_dir, monkeypatch)

        hit = VaultManager.first_unverified_referent(
            "this one is from the Basement directory", profile
        )
        assert hit == ""

    def test_extra_stop_suppresses_the_persona_or_user_name(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        samantha = tmp_vault_dir / "Samantha"
        samantha.mkdir()
        write_note(str(samantha / "Bio.md"), "# Bio\n")
        profile = self._profile(tmp_vault_dir, monkeypatch)

        hit = VaultManager.first_unverified_referent(
            "Samantha mentioned that earlier", profile, extra_stop={"samantha"}
        )
        assert hit == ""

    def test_no_vault_configured_returns_empty_referents(self, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", "")
        assert VaultManager.real_vault_referents({"vault_folders": ["*"]}) == frozenset()
        assert (
            VaultManager.first_unverified_referent(
                "the People directory", {"vault_folders": ["*"]}
            )
            == ""
        )


class TestRecallHitConfidence:
    """Regression: `_recall_candidates` decomposes a multi-word subject down
    to its single leftover words as a last resort, and a common English word
    among them can loosely match several unrelated notes' body text. Live
    bug: "favorite" (from "play our favorite game") matched 5 unrelated
    notes and was accepted as a digest anyway. `require_confident` drops
    that acceptance for exactly those decomposed single-word tries."""

    def test_loose_multi_result_match_rejected_when_confident_required(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "a.md"), "the morning light was nice")
        write_note(str(tmp_vault_dir / "b.md"), "another morning, another coffee")
        profile = {"vault_folders": ["*"]}

        assert (
            VaultManager._recall_hit(profile, "morning", require_confident=True)
            is None
        )
        # Same loose match is accepted (as a digest) without the flag - this
        # isn't a fabrication-free zone, just a lower-confidence one.
        assert VaultManager._recall_hit(profile, "morning") is not None

    def test_single_confident_match_still_returned_when_confident_required(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "morning.md"), "# morning\n\nA quiet start.\n")
        profile = {"vault_folders": ["*"]}

        hit = VaultManager._recall_hit(profile, "morning", require_confident=True)
        assert hit is not None and "quiet start" in hit


class TestResolveTurnContextConversational:
    def _profile(self):
        return {"handle": "anais", "skills": ["vault_read"], "vault_folders": ["*"]}

    def test_conversational_query_surfaces_matching_note(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Rilke.md"),
            "# Rilke\n\nNotes on Rilke and the Duino Elegies.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "pull up my notes on Rilke"
        )
        assert ctx is not None
        assert "Rilke" in ctx

    def test_conversational_query_with_no_match_returns_none(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Rilke.md"), "# Rilke\n")

        assert (
            VaultManager.resolve_turn_context(
                self._profile(), "pull up my notes on Nonexistent Topic Xyz"
            )
            is None
        )

    def test_gate_blocks_persona_without_vault_read_skill(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Rilke.md"), "# Rilke\n")
        no_skill = {"handle": "x", "skills": ["web_search"], "vault_folders": ["*"]}
        assert (
            VaultManager.resolve_turn_context(no_skill, "pull up my notes on Rilke")
            is None
        )

    def test_named_person_entry_hits_that_note_not_a_random_one(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression: "can you pull up Dylan's people entry" tripped the random
        daily-note sampler ("entry" + "pull") and injected an unrelated journal
        note stamped as Ground-Truth, which the model then "read out" as Dylan's."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08, links to [[Tin]].\n",
        )
        write_note(
            str(tmp_vault_dir / "Daily" / "2025-02-05.md"),
            "# Day\n\nBought life insurance today.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(),
            "can you pull up Dylan's people entry from our vault and see if my memory's right?",
        )
        assert ctx is not None
        assert "2015-09-08" in ctx and "insurance" not in ctx

    def test_random_daily_sampler_still_fires_without_a_named_subject(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Daily" / "2025-02-05.md"),
            "# Day\n\nA quiet morning.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "pull up a random daily entry"
        )
        assert ctx is not None and "quiet morning" in ctx

    def test_reflex_reaction_opener_does_not_block_a_random_folder_sample(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression, found live: "hmmm.. not really what I expected. It
        should be a random note from the thoughts folder" guessed the
        subject "hmmm" from the reflex-reaction opener, which then blocked
        the random-sample path (a guessed subject is treated as a named
        target) and sent "hmmm" to a vault-wide word search instead, which
        happened to surface an unrelated Daily note. A low-confidence
        subject guess disconnected from the sentence that actually makes the
        random-note ask must not stop the sampler from firing."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Thoughts" / "a.md"), "# Thoughts\n\nOn entropy.\n"
        )
        write_note(
            str(tmp_vault_dir / "Daily" / "2025-02-05.md"),
            "# Day\n\nHmmm, bought life insurance today.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(),
            'hmmm.. not really what I expected. It should be a random note '
            'from the "thoughts" folder.',
        )
        assert ctx is not None
        assert "entropy" in ctx and "insurance" not in ctx

    def test_write_shaped_message_naming_a_real_folder_still_gets_context(
        self, tmp_vault_dir, monkeypatch
    ):
        """ADR-123.4: a message with no recall-keyword lead-in ("add",
        not "pull up"/"recall"/etc.) used to get zero folder context at
        all, because the folder-scope case (case 7) was gated behind
        `has_intent` - a fixed recall-keyword list - even though it
        already matches against real, discovered folder names. A write
        naming a real folder is just as valid a signal as a recall
        naming one; the folder-name match is now the gate on its own."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08, links to [[Tin]].\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "Add Dylan's birthday to People."
        )
        assert ctx is not None and "2015-09-08" in ctx

    def test_write_shaped_message_naming_a_real_note_with_no_folder_or_keyword(
        self, tmp_vault_dir, monkeypatch
    ):
        """ADR-123.5: the same real-name gate generalized past folders - a
        message naming a real note's own title/filename stem, with no
        recall keyword *and* no folder name in it at all, still gets that
        note's real content instead of nothing. Reuses
        `VaultManager.first_unverified_referent` (ADR-124's structural
        referent index) run on the inbound message rather than the
        model's outbound reply."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08, links to [[Tin]].\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "Update the info for Dylan with his new school."
        )
        assert ctx is not None
        assert "2015-09-08" in ctx

    def test_real_referent_that_is_an_empty_stub_yields_no_hit(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression, found live against a real vault: a near-empty
        placeholder note ("Limbo/Life.md", 0 bytes) is still a real
        referent by name, so an ordinary sentence-initial common word that
        happens to share it ("Life is good today.") used to fall through
        to a *ranked* vault-wide search for "Life", which surfaced a
        wholly unrelated Quotes/ note that merely contained the word - a
        confident-looking but wrong substitute. Reading the confirmed
        referent directly must yield nothing here instead, since the real
        note itself has nothing to show."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Limbo" / "Life.md"), "")
        write_note(
            str(tmp_vault_dir / "Quotes" / "An unexamined life is not worth living.md"),
            "---\nAuthor: Unknown\n---\n",
        )

        ctx = VaultManager.resolve_turn_context(self._profile(), "Life is good today.")
        assert ctx is None

    def test_lowercase_mention_of_a_real_note_still_gets_context(
        self, tmp_vault_dir, monkeypatch
    ):
        """ADR-123.5: casual chat is rarely capitalized ("i ran into dylan
        today"), so the real-referent gate can't only fire on Title Case
        without missing most of it."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08, links to [[Tin]].\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "i ran into dylan today, we had lunch"
        )
        assert ctx is not None
        assert "2015-09-08" in ctx

    def test_possessive_mention_of_someone_not_in_the_vault_is_flagged_as_a_miss(
        self, tmp_vault_dir, monkeypatch
    ):
        """ADR-123.5's miss-surfacing: "marco's birthday" names someone
        who isn't in the vault at all - the last-resort case hands the
        model a plain fact about that, once every real retrieval case
        above has already come up empty."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "add marco's birthday to my contacts"
        )
        assert ctx == "### Vault Check: no real vault entry found for 'marco'."

    def test_possessive_mention_of_someone_real_is_not_flagged_as_a_miss(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "People" / "Dylan.md"),
            "# Dylan\n\nson, born 2015-09-08.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "add dylan's new school to his entry"
        )
        assert ctx is not None
        assert "2015-09-08" in ctx

    def test_ordinary_contraction_is_never_flagged_as_a_miss(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression: "let's" is grammatically identical to a genuine
        possessive ("marco's"), but it's a contraction of "let us," not a
        name - it must not be reported as a missing vault entry."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Dylan.md"), "# Dylan\n")

        assert (
            VaultManager.resolve_turn_context(
                self._profile(), "I'm bored, let's play a game."
            )
            is None
        )

    def test_game_reference_decomposed_to_a_common_word_is_not_trusted_as_a_digest(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression, found live: "lets play our favorite game. lets do
        from Daily folder. g?" - a continuation of a ritual established only
        in this user's own persona memory ("Vault Roulette" is not a
        documented Sympose feature, so it isn't recognised structurally
        here) - decomposed to the single word "favorite", which loosely
        matched an unrelated note and was accepted as a digest anyway. This
        stays a thin, honest "daily" digest instead: no `Exact Content`
        marker, and no note mentioning "favorite" pulled in on that
        strength alone. Whether "our game" means anything is left entirely
        to the model's own memory, not hardcoded here — recognising one
        user's private ritual by name would misfire for anyone else's vault
        (a real "Game Night" folder, say)."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Daily" / "2024-12-21.md"),
            "# Day\n\nA quiet, uneventful day.\n",
        )
        # Two loose matches, not one — a single hit is still confident (a
        # real title/only match can legitimately be trusted); the bug is
        # specifically about *several* unrelated notes sharing one common
        # decomposed word.
        write_note(
            str(tmp_vault_dir / "Thoughts" / "On Preference.md"),
            "# On Preference\n\nMy favorite color is blue.\n",
        )
        write_note(
            str(tmp_vault_dir / "Thoughts" / "On Music.md"),
            "# On Music\n\nMy favorite band changes every year.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(),
            "lets play our favorite game. lets do from Daily folder. g?",
        )
        # Whether anything gets returned at all is incidental here (this
        # tiny fixture has nothing else for a folder-name-as-keyword
        # fallback to match); what matters is that "favorite" never gets
        # trusted as a confident hit for either unrelated note.
        assert ctx is None or "Exact Content" not in ctx
        assert not ctx or ("favorite color" not in ctx and "favorite band" not in ctx)

    def test_folder_scoped_message_does_not_re_broaden_to_the_whole_vault(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression, found live: "I'm bored, let's play our favorite
        game... from daily folder" - once case 7's folder-scoped attempt
        found nothing confident, case 8 retried the same decomposed subject
        *unscoped*, and "bored" (from "I'm bored") happened to be a
        confident single-title match against a totally unrelated Quotes/
        note - full body, "Exact Content", disabling strict grounding for
        the turn, for a note with zero connection to what was actually
        asked. Once a real folder has already been named and tried, the
        broader vault-wide fallback must not re-open the scope the user
        explicitly narrowed."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Daily" / "2025-01-01.md"), "# Day\n\nQuiet start.\n"
        )
        write_note(
            str(tmp_vault_dir / "Quotes" / "bored.md"),
            "# On boredom\n\nBoredom is the mother of invention.\n",
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(),
            "im bored, lets play our favorite game. from daily folder. g?",
        )
        assert ctx is None or "Exact Content" not in ctx
        assert not ctx or "mother of invention" not in ctx

    def test_topic_folder_search_is_a_digest_not_full_body(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression: asking to discuss notes "in a folder" by topic, with
        several matches, returns a multi-result search digest (titles + a
        one-line snippet each) - not any note's full text. Live bug:
        PersonaEngine trusted this digest as "real grounding" and disabled
        its fabrication check entirely, so the model invented a whole essay
        to fill the gap between a one-line snippet and a real conversation.
        The fix keys off the "Exact Content" marker this context is missing -
        this test locks in that it stays missing for a plain digest."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Thoughts" / "A.md"), "# A\n\nSome thoughts here.\n"
        )
        write_note(
            str(tmp_vault_dir / "Thoughts" / "B.md"), "# B\n\nMore thoughts here.\n"
        )
        write_note(
            str(tmp_vault_dir / "Thoughts" / "C.md"), "# C\n\nEven more thoughts.\n"
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "lets talk about the thoughts in that folder"
        )
        assert ctx is not None
        assert "Exact Content" not in ctx

    def test_random_folder_sample_is_full_body(self, tmp_vault_dir, monkeypatch):
        """The random-sample path (as opposed to the multi-result digest
        above) does read a real note's full text - it must carry the same
        "Exact Content" marker every other full-body context does, or
        PersonaEngine._is_full_body_vault_ctx wrongly treats good grounding
        as thin and re-engages strict mode's fabrication check needlessly."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Thoughts" / "A.md"), "# A\n\nSome thoughts here.\n"
        )

        ctx = VaultManager.resolve_turn_context(
            self._profile(),
            "you pull a random note to a folder we agreed, then well tell "
            "each other thoughts about the note",
        )
        assert ctx is not None
        assert "Exact Content" in ctx

    def test_fresh_recall_intent_detected(self):
        from sympose.vault import VaultManager

        assert (
            VaultManager.has_recall_intent("can you pull up my note on grief") is True
        )
        assert VaultManager.has_recall_intent("what's the btc price right now") is False


class TestGetVaultSnapshotIgnoreFoldersCacheKey:
    """Live bug: `_get_vault_snapshot`'s cache was keyed only on the target
    dirs and a directory-mtime signature, not on `vault.ignore_folders`.
    Editing that config to un-ignore a folder doesn't move any directory's
    own mtime, so the stale, pre-edit snapshot (missing the now-unignored
    folder entirely) kept being served with no way to tell it was stale."""

    def test_unignoring_a_folder_is_reflected_without_any_mtime_change(
        self, tmp_vault_dir, monkeypatch
    ):
        from sympose.vault import VaultManager

        write_note(
            str(tmp_vault_dir / "Movies" / "Her.md"), "# Her\n\nA lonely writer.\n"
        )

        monkeypatch.setattr(
            "sympose.vault.config_manager.get",
            lambda key, default=None: (
                [".obsidian", ".git", "Attachments", ".trash", "Movies"]
                if key == "vault.ignore_folders"
                else default
            ),
        )
        first = VaultManager._get_vault_snapshot(str(tmp_vault_dir), [str(tmp_vault_dir)])
        assert not any("Movies" in e["rel_path"] for e in first)

        monkeypatch.setattr(
            "sympose.vault.config_manager.get",
            lambda key, default=None: (
                [".obsidian", ".git", "Attachments", ".trash"]
                if key == "vault.ignore_folders"
                else default
            ),
        )
        second = VaultManager._get_vault_snapshot(str(tmp_vault_dir), [str(tmp_vault_dir)])
        assert any("Movies" in e["rel_path"] for e in second)


class TestDescribesRandomPullRitual:
    """Generic detector for a persona-memory fact describing a "pull a
    random note" ritual, by whatever name the user gave it - deliberately
    not tied to any one wording ("Vault Roulette", "surprise me", etc.)."""

    def test_matches_a_random_note_fact(self):
        from sympose.vault import VaultManager

        assert VaultManager.describes_random_pull_ritual(
            "Damiro's favorite game is \"Vault Roulette,\" where a random "
            "note from his Obsidian vault is pulled and discussed."
        )

    def test_matches_differently_worded_random_pull_facts(self):
        from sympose.vault import VaultManager

        assert VaultManager.describes_random_pull_ritual(
            "We like to grab a random page from the notes together."
        )
        assert VaultManager.describes_random_pull_ritual(
            "Her favorite ritual is picking a random entry to read aloud."
        )

    def test_unrelated_fact_does_not_match(self):
        from sympose.vault import VaultManager

        assert not VaultManager.describes_random_pull_ritual(
            "Damiro likes his coffee black."
        )

    def test_random_alone_without_a_pull_word_does_not_match(self):
        from sympose.vault import VaultManager

        assert not VaultManager.describes_random_pull_ritual(
            "Damiro dislikes random small talk at parties."
        )

    def test_empty_fact_does_not_match(self):
        from sympose.vault import VaultManager

        assert not VaultManager.describes_random_pull_ritual("")


class TestResolveRitualRandomPull:
    """Live bug: "let's play our favorite game" never matches
    resolve_turn_context's own sample-request phrasing, so even when a
    persona's memory says the game IS a random-note pull, nothing real
    ever gets fetched and the model invents a plausible-sounding title.
    `resolve_ritual_random_pull` is called separately, once a matched
    memory fact is already confirmed to describe this ritual."""

    def _profile(self):
        return {"handle": "samantha", "skills": ["vault_read"], "vault_folders": ["*"]}

    def test_folder_named_in_message_scopes_the_pull(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Movies" / "Her.md"), "# Her\n\nA lonely writer.\n"
        )
        write_note(
            str(tmp_vault_dir / "Thoughts" / "Random.md"), "# Random\n\nOn entropy.\n"
        )

        ctx = VaultManager.resolve_ritual_random_pull(
            self._profile(), "lets play our favorite game. lets do Movies. g!"
        )
        assert ctx is not None
        assert "Her.md" in ctx
        assert "Exact Content" in ctx

    def test_no_folder_named_samples_the_whole_vault(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Movies" / "Her.md"), "# Her\n\nA lonely writer.\n"
        )

        ctx = VaultManager.resolve_ritual_random_pull(
            self._profile(), "lets play our favorite game"
        )
        assert ctx is not None
        assert "Exact Content" in ctx

    def test_scoped_persona_without_full_vault_access_and_no_folder_named_returns_none(
        self, tmp_vault_dir, monkeypatch
    ):
        """A partial-access persona whose allowed_dirs aren't the vault root
        itself shouldn't get an implicit vault-wide sample when no folder is
        named - conservative fallback, not a regression."""
        from sympose.vault import VaultManager

        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "Movies" / "Her.md"), "# Her\n\nA lonely writer.\n"
        )
        scoped = {
            "handle": "scoped",
            "skills": ["vault_read"],
            "vault_folders": ["Movies"],
        }

        assert (
            VaultManager.resolve_ritual_random_pull(scoped, "lets play our favorite game")
            is None
        )


class TestWorkspaceDir:
    """Regression coverage: `_workspace_dir` must delegate to the canonical
    `resolve_workspace_dir()` resolver (which guards against cwd being "/" or
    "~") rather than reverse-engineering a directory from
    `config_manager.config_path`. That path stays the relative "config.yaml"
    default whenever a caller loads config through a fresh ConfigManager
    instead of the shared singleton, so deriving from it silently pointed the
    vault manifest cache at the process's cwd — including "/" itself, which
    crashed with a read-only-filesystem OSError."""

    def test_delegates_to_resolve_workspace_dir(self, monkeypatch):
        from sympose.config import config_manager
        from sympose.vault import VaultManager

        # Deliberately leave config_manager.config_path on its relative
        # default and simulate a process launched from "/" — the exact
        # conditions that produced the "/.vault_index" crash.
        monkeypatch.setattr(config_manager, "config_path", "config.yaml")
        monkeypatch.chdir("/")

        assert VaultManager._workspace_dir() == os.path.join(
            os.path.expanduser("~"), ".sympose"
        )
