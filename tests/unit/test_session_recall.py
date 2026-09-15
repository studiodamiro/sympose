"""
Unit tests for sympose.session_recall.has_session_recall_intent — the
deterministic detector that tells the engine "this is asking about a past
Sympose conversation," never the Obsidian vault.
"""

from sympose.session_recall import has_session_recall_intent


class TestSessionRecallIntent:
    def test_what_did_we_do_last_session(self):
        assert has_session_recall_intent("tell me, what did we do last session?")

    def test_what_did_we_talk_about_yesterday(self):
        assert has_session_recall_intent("what did we talk about yesterday")

    def test_our_last_conversation(self):
        assert has_session_recall_intent("can you recap our last conversation?")

    def test_pick_up_where_we_left_off(self):
        assert has_session_recall_intent("let's pick up where we left off")

    def test_catch_me_up(self):
        assert has_session_recall_intent("catch me up on our previous session")

    def test_what_were_we_working_on(self):
        assert has_session_recall_intent("what were we working on before?")

    def test_plain_greeting_is_not_session_recall(self):
        assert not has_session_recall_intent("hey sam, you here?")

    def test_vault_journal_question_is_not_session_recall(self):
        assert not has_session_recall_intent(
            "what did I write about grief in my journal?"
        )

    def test_unrelated_question_mentioning_last_is_not_session_recall(self):
        assert not has_session_recall_intent("what was the last movie I rated 5 stars?")
