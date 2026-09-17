"""
Unit tests for sympose.vault_links — wikilink extraction and the inverted
backlink index built from it.
"""

import os
import time

from sympose import vault_links


def write_note(path, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestExtractWikilinks:
    def test_plain_link(self):
        links = vault_links.extract_wikilinks("See [[Grief]] for details.")
        assert len(links) == 1
        assert links[0]["target"] == "Grief"
        assert links[0]["stem"] == "grief"
        assert links[0]["heading"] is None
        assert links[0]["alias"] is None

    def test_link_with_heading_and_alias(self):
        links = vault_links.extract_wikilinks("[[Grief#Stages|the stages]]")
        assert links[0]["target"] == "Grief"
        assert links[0]["heading"] == "Stages"
        assert links[0]["alias"] == "the stages"

    def test_folder_path_target_uses_basename_as_stem(self):
        links = vault_links.extract_wikilinks("[[People/Dylan]]")
        assert links[0]["target"] == "People/Dylan"
        assert links[0]["stem"] == "dylan"

    def test_no_links_returns_empty_list(self):
        assert vault_links.extract_wikilinks("just plain text") == []

    def test_multiple_links(self):
        links = vault_links.extract_wikilinks("[[A]] and [[B]] and [[C]]")
        assert [link["target"] for link in links] == ["A", "B", "C"]


class TestGetForwardLinks:
    def test_delegates_to_read_note_fn_and_extracts(self):
        calls = []

        def fake_read_note(profile, note_name):
            calls.append((profile, note_name))
            return "See [[Target]] here."

        result = vault_links.get_forward_links(
            {"handle": "sam"}, "Source.md", read_note_fn=fake_read_note
        )
        assert calls == [({"handle": "sam"}, "Source.md")]
        assert result[0]["target"] == "Target"

    def test_empty_when_note_not_found(self):
        result = vault_links.get_forward_links(
            {},
            "Missing.md",
            read_note_fn=lambda profile, name: "Note `Missing.md` not found.",
        )
        assert result == []

    def test_empty_when_read_note_returns_warning(self):
        result = vault_links.get_forward_links(
            {}, "X.md", read_note_fn=lambda profile, name: "⚠️ Access denied."
        )
        assert result == []


class TestBacklinkCache:
    def test_cache_populated_on_first_call(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(
            str(tmp_vault_dir / "source.md"), "# Source\nSee [[target]] for details."
        )
        vault_links.build_backlink_index(profile)
        assert len(vault_links._BACKLINK_CACHE) >= 1

    def test_cache_hit_on_second_call(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "doc.md"), "[[linked]]")
        result1 = vault_links.build_backlink_index(profile)
        result2 = vault_links.build_backlink_index(profile)
        assert result1 == result2

    def test_cache_invalidated_after_file_change(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "changing.md"), "[[link_one]]")
        vault_links.build_backlink_index(profile)
        time.sleep(0.05)
        write_note(str(tmp_vault_dir / "new_file.md"), "new")
        result2 = vault_links.build_backlink_index(profile)
        assert isinstance(result2, dict)

    def test_clear_cache_forces_a_rebuild(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "a.md"), "[[b]]")
        vault_links.build_backlink_index(profile)
        assert vault_links._BACKLINK_CACHE
        vault_links.clear_cache()
        assert vault_links._BACKLINK_CACHE == {}


class TestGetBacklinks:
    def test_finds_incoming_references(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "Referrer.md"), "Mentions [[Target]] here.")
        result = vault_links.get_backlinks(profile, "Target")
        assert len(result) == 1
        assert result[0]["rel_path"] == "Referrer.md"

    def test_no_matches_returns_empty_list(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "Lone.md"), "no links here")
        assert vault_links.get_backlinks(profile, "Nothing") == []


class TestGetBacklinksDigest:
    def test_no_backlinks_message(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        digest = vault_links.get_backlinks_digest({"vault_folders": ["*"]}, "Ghost")
        assert "No backlinks found" in digest

    def test_formats_found_backlinks_with_context(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        write_note(str(tmp_vault_dir / "Referrer.md"), "Mentions [[Target]] here.")
        digest = vault_links.get_backlinks_digest(profile, "Target")
        assert "Referrer.md" in digest
        assert "Mentions [[Target]] here." in digest

    def test_truncates_past_max_entries(self, tmp_vault_dir, monkeypatch):
        vault_links.clear_cache()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        profile = {"vault_folders": ["*"]}
        for i in range(3):
            write_note(str(tmp_vault_dir / f"Ref{i}.md"), "[[Target]]")
        digest = vault_links.get_backlinks_digest(profile, "Target", max_entries=1)
        assert "+ 2 more references" in digest
