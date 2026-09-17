"""
Unit tests for sympose.vault_grounding — the structural (not phrase-based)
grounding check added by ADR-124. Pure functions, no VaultManager/I-O
needed: real vault data is handed in exactly as VaultManager.
real_vault_referents builds it (folder-name keys from directory discovery,
plus filename stems and frontmatter titles from the note snapshot).
"""

import re

from sympose import vault_grounding
from sympose.vault import VAULT_PATH_TOKEN_RE


class TestExtractReferentCandidates:
    def test_finds_capitalized_runs(self):
        cands = vault_grounding.extract_referent_candidates(
            "this one is from the People directory", VAULT_PATH_TOKEN_RE
        )
        assert "People" in cands

    def test_finds_multi_word_title_case_run(self):
        cands = vault_grounding.extract_referent_candidates(
            "check General/Personal Philosophy.md for that", VAULT_PATH_TOKEN_RE
        )
        assert any("Personal Philosophy" in c for c in cands)

    def test_finds_path_shaped_tokens(self):
        cands = vault_grounding.extract_referent_candidates(
            "Source: People/Dylan.md", VAULT_PATH_TOKEN_RE
        )
        assert "People/Dylan.md" in cands

    def test_empty_text_yields_no_candidates(self):
        assert vault_grounding.extract_referent_candidates("", VAULT_PATH_TOKEN_RE) == []

    def test_no_capitals_yields_no_candidates(self):
        assert (
            vault_grounding.extract_referent_candidates(
                "nothing capitalized in here at all", VAULT_PATH_TOKEN_RE
            )
            == []
        )


class TestRealVaultReferentsFromSnapshot:
    def test_folder_names_included(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {"people": "/vault/People", "movies": "/vault/Movies"}, []
        )
        assert real == {"people", "movies"}

    def test_note_filename_stem_included(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {}, [{"file_name": "Dylan.md", "meta": {}}]
        )
        assert "dylan" in real

    def test_frontmatter_title_included(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {}, [{"file_name": "note1.md", "meta": {"title": "Wild Card Note Pull"}}]
        )
        assert "wild card note pull" in real

    def test_missing_or_non_dict_meta_is_skipped_safely(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {}, [{"file_name": "a.md"}, {"file_name": "b.md", "meta": None}]
        )
        assert real == {"a", "b"}


class TestFirstUnverifiedReferent:
    def _real(self):
        return vault_grounding.real_vault_referents_from_snapshot(
            {"people": "/vault/People"},
            [{"file_name": "Dylan.md", "meta": {}}],
        )

    def test_catches_a_real_folder_named_with_no_recognized_phrasing(self):
        """The exact live gap this ADR closes: 'this one is from the People
        directory' matches none of engine.py's `_VAULT_CLAIM_RE` phrases,
        but names a real folder."""
        hit = vault_grounding.first_unverified_referent(
            "this one is from the People directory", VAULT_PATH_TOKEN_RE, self._real()
        )
        assert hit == "People"

    def test_catches_a_real_note_stem(self):
        hit = vault_grounding.first_unverified_referent(
            "I found something about Dylan earlier", VAULT_PATH_TOKEN_RE, self._real()
        )
        assert hit == "Dylan"

    def test_no_hit_when_nothing_named_is_real(self):
        hit = vault_grounding.first_unverified_referent(
            "This one is from the Nonexistent directory",
            VAULT_PATH_TOKEN_RE,
            self._real(),
        )
        assert hit == ""

    def test_extra_stop_suppresses_a_match(self):
        hit = vault_grounding.first_unverified_referent(
            "this one is from the People directory",
            VAULT_PATH_TOKEN_RE,
            self._real(),
            extra_stop={"people"},
        )
        assert hit == ""

    def test_empty_real_referents_never_matches(self):
        hit = vault_grounding.first_unverified_referent(
            "the People directory has it", VAULT_PATH_TOKEN_RE, frozenset()
        )
        assert hit == ""

    def test_returns_first_match_in_appearance_order(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {"people": "/x", "movies": "/y"}, []
        )
        hit = vault_grounding.first_unverified_referent(
            "somewhere between Movies and People", VAULT_PATH_TOKEN_RE, real
        )
        assert hit == "Movies"


def test_capitalized_run_regex_is_reused_consistently():
    # Sanity check that the module's own extraction regex is a plain
    # re.Pattern usable the same way VAULT_PATH_TOKEN_RE is.
    assert isinstance(vault_grounding._CAPITALIZED_RUN_RE, re.Pattern)
