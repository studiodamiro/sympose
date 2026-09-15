"""
Characterization + unit tests for vault search: written against
VaultManager.search_structured/search/format_search_digest/get_last_search
*before* that logic moved out of vault.py into vault_search.py (this
cluster had zero test coverage until this file), then kept passing
unchanged afterward — VaultManager's public API is the same either way, so
these tests prove the move didn't change behavior.
"""

import os

from sympose.vault import VaultManager


def write_note(path, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestSearchStructuredTitleMatch:
    def test_filename_match_classified_as_title(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Grief.md"), "# Grief\nSome content here.")
        results = VaultManager.search_structured({"vault_folders": ["*"]}, "grief")
        assert len(results) == 1
        assert results[0]["match_type"] == "title"
        assert results[0]["rel_path"] == "Grief.md"

    def test_folder_name_coincidence_is_not_a_title_match(
        self, tmp_vault_dir, monkeypatch
    ):
        """Regression: a query matching an ancestor *folder* name used to
        flood title matches for every note in that folder — only the
        filename itself should count."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Quotes" / "life.md"), "no match text here")
        results = VaultManager.search_structured({"vault_folders": ["*"]}, "quote")
        assert results == []


class TestSearchStructuredTagMatch:
    def test_tag_match_takes_priority_over_content_match(
        self, tmp_vault_dir, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "note.md"),
            "---\ntags: [urgent]\n---\n\nThis mentions urgent things too.",
        )
        results = VaultManager.search_structured({"vault_folders": ["*"]}, "urgent")
        assert len(results) == 1
        assert results[0]["match_type"] == "tag"


class TestSearchStructuredContentMatch:
    def test_content_match_with_snippet(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(
            str(tmp_vault_dir / "journal.md"),
            "line one\nline two mentions Rilke here\nline three",
        )
        results = VaultManager.search_structured({"vault_folders": ["*"]}, "rilke")
        assert len(results) == 1
        assert results[0]["match_type"] == "content"
        assert results[0]["line_no"] == 2
        assert "Rilke" in results[0]["snippet"]

    def test_no_match_returns_empty_list(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "note.md"), "nothing relevant")
        assert (
            VaultManager.search_structured({"vault_folders": ["*"]}, "nonexistentxyz")
            == []
        )

    def test_empty_query_returns_empty_list(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        assert VaultManager.search_structured({"vault_folders": ["*"]}, "   ") == []

    def test_no_vault_configured_returns_empty_list(self, monkeypatch):
        monkeypatch.delenv("MASTER_VAULT_PATH", raising=False)
        assert VaultManager.search_structured({"vault_folders": ["*"]}, "x") == []


class TestSearchStructuredTargetFolder:
    def test_restricts_to_named_folder(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Notes" / "a.md"), "mentions widget")
        write_note(str(tmp_vault_dir / "Journal" / "b.md"), "also mentions widget")
        results = VaultManager.search_structured(
            {"vault_folders": ["Notes", "Journal"]}, "widget", target_folder="Notes"
        )
        assert len(results) == 1
        assert results[0]["rel_path"] == "Notes/a.md"

    def test_restricts_to_a_subfolder_of_a_wildcard_persona(
        self, tmp_vault_dir, monkeypatch
    ):
        # A wildcard (`vault_folders: ["*"]`) persona's only allowed_dir is
        # the vault root itself — "Notes" never appears in that list by
        # name, only as a subfolder under it. Regression: this used to make
        # the folder filter match nothing, which silently fell through to
        # searching the whole vault instead of just "Notes" (see the
        # unresolvable-folder test below for that old fallback's replacement).
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Notes" / "a.md"), "mentions widget")
        write_note(str(tmp_vault_dir / "Journal" / "b.md"), "also mentions widget")
        results = VaultManager.search_structured(
            {"vault_folders": ["*"]}, "widget", target_folder="Notes"
        )
        assert len(results) == 1
        assert results[0]["rel_path"] == "Notes/a.md"

    def test_unresolvable_target_folder_returns_nothing_rather_than_everything(
        self, tmp_vault_dir, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Notes" / "a.md"), "mentions widget")
        results = VaultManager.search_structured(
            {"vault_folders": ["*"]}, "widget", target_folder="NoSuchFolder"
        )
        assert results == []


class TestSearchStructuredMaxResults:
    def test_caps_at_max_results(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        for i in range(5):
            write_note(str(tmp_vault_dir / f"n{i}.md"), "mentions widget here")
        results = VaultManager.search_structured(
            {"vault_folders": ["*"]}, "widget", max_results=2
        )
        assert len(results) == 2
        assert [r["index"] for r in results] == [1, 2]


class TestGetLastSearch:
    def test_stores_results_per_persona_handle(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "a.md"), "mentions widget")
        VaultManager.search_structured(
            {"handle": "sam", "vault_folders": ["*"]}, "widget"
        )
        assert VaultManager.get_last_search({"handle": "sam"}) != []

    def test_no_leak_between_personas(self, tmp_vault_dir, monkeypatch):
        """A shared fallback key would let persona A's results leak into
        persona B's /read <n> if B hasn't searched yet."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "a.md"), "mentions widget")
        VaultManager.search_structured(
            {"handle": "sam", "vault_folders": ["*"]}, "widget"
        )
        assert VaultManager.get_last_search({"handle": "grace"}) == []

    def test_empty_before_any_search(self):
        assert VaultManager.get_last_search({"handle": "fresh"}) == []


class TestFormatSearchDigest:
    def test_no_results_message(self):
        digest = VaultManager.format_search_digest("nope", [])
        assert "No notes found matching" in digest
        assert "nope" in digest

    def test_formats_title_match(self):
        results = [
            {
                "index": 1,
                "rel_path": "Grief.md",
                "match_type": "title",
                "line_no": 1,
                "snippet": "Exact title match",
                "tags": ["journal"],
            }
        ]
        digest = VaultManager.format_search_digest("grief", results)
        assert "[1] `Grief.md`" in digest
        assert "(Title Match)" in digest
        assert "#journal" in digest

    def test_formats_content_match_with_line_number(self):
        results = [
            {
                "index": 1,
                "rel_path": "j.md",
                "match_type": "content",
                "line_no": 7,
                "snippet": "the matching line",
                "tags": [],
            }
        ]
        digest = VaultManager.format_search_digest("x", results)
        assert "(Line 7)" in digest
        assert "the matching line" in digest


class TestSearch:
    def test_composes_structured_search_and_digest(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        write_note(str(tmp_vault_dir / "Grief.md"), "content")
        digest = VaultManager.search({"vault_folders": ["*"]}, "grief")
        assert "Grief.md" in digest
        assert "Title Match" in digest

    def test_no_match_digest(self, tmp_vault_dir, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        digest = VaultManager.search({"vault_folders": ["*"]}, "nothingxyz")
        assert "No notes found matching" in digest
