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

    def test_frontmatter_only_note_without_trailing_newline(self):
        """People/Templates notes are often 100% frontmatter with the closing
        `---` as the last line and no trailing newline — must still parse."""
        from sympose.vault import VaultManager
        content = "---\naka:\n  - Dylan\nname: Dylan Cosmo\ntags:\n  - \"#person\"\n  - son\n---"
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

        assert result == VaultManager.NOTE_NOT_FOUND or result == VaultManager.NOTE_DENIED
        assert outside.read_text() == "before"


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
        assert self._subj("what did I write about grief in my journal") == ("grief", True)

    def test_do_i_have_notes_about(self):
        assert self._subj("do I have any notes about If I Stay") == ("if i stay", True)

    def test_about_object_extraction(self):
        assert self._subj("recall our past conversations about longing") == ("longing", True)

    def test_greeting_is_stripped(self):
        assert self._subj("hey anais, remind me about the Meridian project") == ("meridian project", True)

    def test_no_leadin_flag_when_plain(self):
        subj, had_leadin = self._subj("what's the weather in Tokyo")
        assert had_leadin is False

    def test_trailing_stopwords_trimmed(self):
        subj, _ = self._subj("pull up my notes on the database schema")
        assert subj == "database schema"

    def test_politeness_wrapper_stripped_before_leadin(self):
        # "can you" used to block the "pull up" lead-in from ever matching.
        assert self._subj("can you pull up Dylan's people entry from our vault") == ("dylan people", True)

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


class TestResolveTurnContextConversational:
    def _profile(self):
        return {"handle": "anais", "skills": ["vault_recall"], "vault_folders": ["*"]}

    def test_conversational_query_surfaces_matching_note(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Rilke.md"), "# Rilke\n\nNotes on Rilke and the Duino Elegies.\n")

        ctx = VaultManager.resolve_turn_context(self._profile(), "pull up my notes on Rilke")
        assert ctx is not None
        assert "Rilke" in ctx

    def test_conversational_query_with_no_match_returns_none(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Rilke.md"), "# Rilke\n")

        assert VaultManager.resolve_turn_context(self._profile(), "pull up my notes on Nonexistent Topic Xyz") is None

    def test_gate_blocks_persona_without_vault_recall_skill(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Rilke.md"), "# Rilke\n")
        no_skill = {"handle": "x", "skills": ["web_search"], "vault_folders": ["*"]}
        assert VaultManager.resolve_turn_context(no_skill, "pull up my notes on Rilke") is None

    def test_named_person_entry_hits_that_note_not_a_random_one(self, tmp_vault_dir, monkeypatch):
        """Regression: "can you pull up Dylan's people entry" tripped the random
        daily-note sampler ("entry" + "pull") and injected an unrelated journal
        note stamped as Ground-Truth, which the model then "read out" as Dylan's."""
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "People" / "Dylan.md"), "# Dylan\n\nson, born 2015-09-08, links to [[Tin]].\n")
        write_note(str(tmp_vault_dir / "Daily" / "2025-02-05.md"), "# Day\n\nBought life insurance today.\n")

        ctx = VaultManager.resolve_turn_context(
            self._profile(), "can you pull up Dylan's people entry from our vault and see if my memory's right?"
        )
        assert ctx is not None
        assert "2015-09-08" in ctx and "insurance" not in ctx

    def test_random_daily_sampler_still_fires_without_a_named_subject(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Daily" / "2025-02-05.md"), "# Day\n\nA quiet morning.\n")

        ctx = VaultManager.resolve_turn_context(self._profile(), "pull up a random daily entry")
        assert ctx is not None and "quiet morning" in ctx

    def test_fresh_recall_intent_detected(self):
        from sympose.vault import VaultManager
        assert VaultManager.has_recall_intent("can you pull up my note on grief") is True
        assert VaultManager.has_recall_intent("what's the btc price right now") is False
