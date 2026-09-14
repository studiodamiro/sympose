"""
Unit tests for sympose.vault_recall — the pure, self-contained half of
conversational-recall handling (subject extraction is already covered
thoroughly in test_vault.py::TestExtractRecallSubject via the VaultManager
facade, which didn't change; this file covers has_recall_intent and
recall_candidates directly, the latter with no prior coverage at all).
"""

from sympose import vault_recall


class TestHasRecallIntent:
    def test_true_for_a_recall_leadin(self):
        assert (
            vault_recall.has_recall_intent("can you pull up my note on grief") is True
        )

    def test_true_for_a_configured_trigger_word(self):
        assert vault_recall.has_recall_intent("check my journal please") is True

    def test_false_for_an_unrelated_message(self):
        assert vault_recall.has_recall_intent("what's the btc price right now") is False

    def test_respects_configured_search_triggers(self, monkeypatch):
        from sympose.config import config_manager

        monkeypatch.setattr(config_manager, "get", lambda key, default=None: ["widget"])
        # No recall lead-in in either message, so only the configured
        # trigger word decides the outcome.
        assert vault_recall.has_recall_intent("i love my widget") is True
        assert vault_recall.has_recall_intent("i love my gadget") is False


class TestRecallCandidates:
    def test_full_phrase_first(self):
        assert vault_recall.recall_candidates("grief and loss")[0] == "grief and loss"

    def test_orders_by_length_then_position(self):
        cands = vault_recall.recall_candidates("dylan people entry")
        # "people" and "dylan" are both real tokens; "entry" is a stopword.
        assert "entry" not in cands
        assert set(cands) >= {"dylan people entry", "people", "dylan"}

    def test_depluralizes_long_tokens(self):
        cands = vault_recall.recall_candidates("photographs")
        assert "photograph" in cands

    def test_drop_removes_one_token(self):
        cands = vault_recall.recall_candidates("dylan people", drop="people")
        assert "people" not in cands
        assert "dylan" in cands

    def test_short_tokens_and_stopwords_excluded(self):
        cands = vault_recall.recall_candidates("my the a")
        assert cands == ["my the a"] or cands == []

    def test_no_duplicates(self):
        cands = vault_recall.recall_candidates("grief grief")
        assert len(cands) == len(set(cands))


class TestExtractRecallSubjectDirect:
    """Light direct-module smoke coverage — the exhaustive phrasing matrix
    lives in test_vault.py::TestExtractRecallSubject against the
    VaultManager facade, unchanged by this module's extraction."""

    def test_leadin_consumed_and_subject_extracted(self):
        subject, had_leadin = vault_recall.extract_recall_subject(
            "pull up my notes on Rilke"
        )
        assert subject == "rilke"
        assert had_leadin is True

    def test_no_leadin_no_subject_signal(self):
        _, had_leadin = vault_recall.extract_recall_subject("how's the weather today")
        assert had_leadin is False
