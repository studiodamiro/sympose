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


class TestRealReferentMentioned:
    """ADR-123.5: the case-insensitive counterpart to
    first_unverified_referent, for inbound chat that can't be assumed to
    follow Title-Case conventions the way a model's own reply usually
    does."""

    def _real(self):
        return vault_grounding.real_vault_referents_from_snapshot(
            {"people": "/vault/People"},
            [{"file_name": "Dylan.md", "meta": {}}],
        )

    def test_catches_an_all_lowercase_mention(self):
        hit = vault_grounding.real_referent_mentioned(
            "i ran into dylan today, we had lunch", self._real()
        )
        assert hit == "dylan"

    def test_possessive_form_still_resolves_to_the_bare_name(self):
        """"dylan's" tokenizes on the apostrophe into "dylan" + "s", so a
        possessive mention needs no separate stripping step to match."""
        hit = vault_grounding.real_referent_mentioned(
            "can you update dylan's school info", self._real()
        )
        assert hit == "dylan"

    def test_name_embedded_in_a_longer_phrase_is_not_swallowed(self):
        """Regression: a naive greedy 3-word window ("ran into dylan")
        would consume "dylan" into a candidate that matches nothing and
        never try it alone. Every window size is tried at every position."""
        hit = vault_grounding.real_referent_mentioned(
            "i ran into dylan today", self._real()
        )
        assert hit == "dylan"

    def test_no_hit_on_ordinary_conversational_text(self):
        assert (
            vault_grounding.real_referent_mentioned(
                "the weather today is really nice, dont you think", self._real()
            )
            == ""
        )

    def test_multi_word_referent_matches_as_one_window(self):
        real = vault_grounding.real_vault_referents_from_snapshot(
            {}, [{"file_name": "note1.md", "meta": {"title": "If I Stay"}}]
        )
        hit = vault_grounding.real_referent_mentioned("have you read if i stay", real)
        assert hit == "if i stay"

    def test_extra_stop_suppresses_a_match(self):
        assert (
            vault_grounding.real_referent_mentioned(
                "dylan is around", self._real(), extra_stop={"dylan"}
            )
            == ""
        )

    def test_empty_real_referents_never_matches(self):
        assert (
            vault_grounding.real_referent_mentioned("dylan is around", frozenset())
            == ""
        )


class TestPossessiveMentions:
    """ADR-123.5's miss-surfacing side: a possessive is a
    capitalization-independent signal of naming a specific thing, but
    English contracts plenty of pronouns/adverbs with "'s" too - those
    must not be mistaken for a possessive."""

    def test_finds_a_genuine_possessive(self):
        assert vault_grounding.possessive_mentions(
            "add marco's birthday to my contacts"
        ) == ["marco"]

    def test_finds_multiple_in_appearance_order(self):
        assert vault_grounding.possessive_mentions(
            "marco's birthday and kevin's new place"
        ) == ["marco", "kevin"]

    def test_excludes_common_contractions(self):
        for msg in (
            "that's a great idea",
            "here's what I was thinking",
            "there's nothing to worry about",
            "who's coming to the party",
            "what's the plan for today",
            "let's play a game",
            "one's own thoughts can be tricky",
        ):
            assert vault_grounding.possessive_mentions(msg) == []

    def test_excludes_personal_and_indefinite_pronouns(self):
        for msg in (
            "she's doing great",
            "he's been busy lately",
            "everyone's excited about the trip",
            "nobody's perfect, right?",
        ):
            assert vault_grounding.possessive_mentions(msg) == []

    def test_excludes_temporal_deictic_nouns(self):
        for msg in ("today's a good day", "tomorrow's forecast looks clear"):
            assert vault_grounding.possessive_mentions(msg) == []

    def test_no_possessive_yields_empty_list(self):
        assert vault_grounding.possessive_mentions("just chatting, nothing else") == []
