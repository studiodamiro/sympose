"""Tests for sympose.engine.followup (docs/decisions/017, 021): when a message is
rewritten (an empty first search with earlier conversation, or a weak one), what
the rewrite is shown, and that every way the step can fail leaves the turn
grounded exactly as before. Retrieval on the fixture vault is
covered by the follow-up cases in test_grounding_eval.py."""

import pytest

from sympose import settings_store
from sympose.engine import budget, followup, grounding
from sympose.engine.model import EngineModelError, ModelReply, ReplyLimitError

HISTORY = [
    {"role": "user", "content": "what did we decide about the database for Atlas?"},
    {"role": "assistant", "content": "You decided on SQLite for the Atlas prototype."},
]
HIT = {"rel_path": "Projects/Atlas.md", "text": "SQLite", "title": "Atlas", "index": 1}
# What the retriever reports (docs/decisions/021): one matched word is weak evidence.
WEAK = {**HIT, "matched": 1}
STRONG = {**HIT, "matched": 2}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(followup.vault_paths, "resolve_sandbox", lambda persona: ("/vault", ["*"]))
    monkeypatch.setattr(followup, "_CANNOT_REWRITE", set())


def fake_ground(monkeypatch, answers: dict[str, list]):
    """Stands in for the retriever: the hits for a query, `[]` for any other."""
    asked: list[str] = []

    def ground(persona, message, max_results=5):
        asked.append(message)
        return list(answers.get(message, []))

    monkeypatch.setattr(grounding, "ground", ground)
    return asked


def fake_model(monkeypatch, text: str | Exception, truncated: bool = False):
    """Stands in for the model call; returns what it was sent."""
    calls: list[dict] = []

    def call_model(messages, model=None, num_ctx=None, max_tokens=None):
        calls.append({"messages": messages, "model": model, "num_ctx": num_ctx, "max_tokens": max_tokens})
        if isinstance(text, Exception):
            raise text
        return ModelReply(text, 5, truncated=truncated)

    monkeypatch.setattr(followup.model_mod, "call_model", call_model)
    return calls


def rewriter(answer: str | None):
    asked: list[tuple] = []

    def rewrite(history, message, model, limits):
        asked.append((history, message, model))
        return answer

    rewrite.asked = asked
    return rewrite


# --- ground: when the step runs ---


def test_a_message_that_grounds_on_its_own_never_runs_the_rewrite(monkeypatch):
    fake_ground(monkeypatch, {"why SQLite?": [HIT]})
    rw = rewriter("unused")
    assert followup.ground({}, "why SQLite?", HISTORY, "m", None, rewriter=rw) == ([HIT], None)
    assert rw.asked == []


def test_with_no_earlier_turns_there_is_nothing_to_rewrite_from(monkeypatch):
    fake_ground(monkeypatch, {})
    rw = rewriter("Atlas")
    assert followup.ground({}, "why did we pick it?", [], "m", None, rewriter=rw) == ([], None)
    assert rw.asked == []


def test_a_miss_with_history_is_searched_again_on_the_rewritten_query(monkeypatch):
    asked = fake_ground(monkeypatch, {"why did we pick SQLite for Atlas": [HIT]})
    rw = rewriter("why did we pick SQLite for Atlas")
    hits, query = followup.ground({}, "why did we pick it?", HISTORY, "some-model", None, rewriter=rw)
    assert (hits, query) == ([HIT], "why did we pick SQLite for Atlas")
    assert asked == ["why did we pick it?", "why did we pick SQLite for Atlas"]
    assert rw.asked == [(HISTORY, "why did we pick it?", "some-model")]


def test_a_rewrite_that_finds_nothing_reports_no_query(monkeypatch):
    fake_ground(monkeypatch, {})
    assert followup.ground({}, "what about that?", HISTORY, "m", None, rewriter=rewriter("tax filing")) == ([], None)


def test_no_rewrite_means_no_second_search(monkeypatch):
    asked = fake_ground(monkeypatch, {})
    assert followup.ground({}, "thanks!", HISTORY, "m", None, rewriter=rewriter(None)) == ([], None)
    assert asked == ["thanks!"]


def test_a_rewrite_equal_to_the_message_is_not_searched_twice(monkeypatch):
    asked = fake_ground(monkeypatch, {})
    followup.ground({}, "hello there", HISTORY, "m", None, rewriter=rewriter("hello there"))
    assert asked == ["hello there"]


def test_a_persona_with_no_vault_never_runs_the_rewrite(monkeypatch):
    fake_ground(monkeypatch, {"q": [HIT]})
    monkeypatch.setattr(followup.vault_paths, "resolve_sandbox", lambda persona: None)
    rw = rewriter("q")
    assert followup.ground({}, "it?", HISTORY, "m", None, rewriter=rw) == ([], None)
    assert rw.asked == []


def test_the_knob_turns_the_step_off_only_when_explicitly_off(monkeypatch):
    fake_ground(monkeypatch, {"q": [HIT]})
    rw = rewriter("q")
    settings_store.set(followup.SETTING, "off")
    assert followup.ground({}, "it?", HISTORY, "m", None, rewriter=rw) == ([], None)
    assert rw.asked == []
    # The reserved modes and junk leave the default (rewrite) on.
    for value in ("recent-words", "model-searches", "OFF", "", None, False, 0):
        settings_store.set(followup.SETTING, value)
        assert followup.ground({}, "it?", HISTORY, "m", None, rewriter=rw) == ([HIT], "q"), value


# --- ground: weak evidence (docs/decisions/021) ---


def test_strong_evidence_never_runs_the_rewrite(monkeypatch):
    fake_ground(monkeypatch, {"atlas database": [STRONG]})
    rw = rewriter("unused")
    assert followup.ground({}, "atlas database", HISTORY, "m", None, rewriter=rw) == ([STRONG], None)
    assert rw.asked == []


def test_one_strong_hit_among_weak_ones_is_strong_evidence(monkeypatch):
    fake_ground(monkeypatch, {"q": [WEAK, STRONG]})
    rw = rewriter("unused")
    assert followup.ground({}, "q", HISTORY, "m", None, rewriter=rw) == ([WEAK, STRONG], None)
    assert rw.asked == []


@pytest.mark.parametrize("history", [HISTORY, []])
def test_weak_evidence_is_put_to_the_rewrite_with_or_without_earlier_turns(monkeypatch, history):
    fake_ground(monkeypatch, {"hey there": [WEAK]})
    rw = rewriter(followup.NO_TOPIC_QUERY)
    assert followup.ground({}, "hey there", history, "m", None, rewriter=rw) == ([], None)
    assert len(rw.asked) == 1  # NONE: the weak hits are dropped


def test_weak_evidence_is_replaced_by_the_rewritten_querys_hits(monkeypatch):
    asked = fake_ground(monkeypatch, {"where did you get this information?": [WEAK], "Atlas database": [STRONG]})
    result = followup.ground({}, "where did you get this information?", HISTORY, "m", None, rewriter=rewriter("Atlas database"))
    assert result == ([STRONG], "Atlas database")
    assert asked == ["where did you get this information?", "Atlas database"]


def test_weak_evidence_and_a_rewrite_that_finds_nothing_grounds_nothing(monkeypatch):
    fake_ground(monkeypatch, {"m": [WEAK]})
    assert followup.ground({}, "m", HISTORY, "m", None, rewriter=rewriter("something else")) == ([], None)


def test_weak_evidence_stands_when_the_model_vouches_for_the_message_as_it_is(monkeypatch):
    asked = fake_ground(monkeypatch, {"who is Priya?": [WEAK]})
    assert followup.ground({}, "who is Priya?", [], "m", None, rewriter=rewriter("who is Priya?")) == ([WEAK], None)
    assert asked == ["who is Priya?"]  # and is not searched twice


@pytest.mark.parametrize("query", ["who is priya", "Who is Priya", "who is  Priya??"])
def test_a_query_that_differs_only_in_case_or_punctuation_is_the_message_itself(monkeypatch, query):
    asked = fake_ground(monkeypatch, {"who is Priya?": [WEAK]})
    assert followup.ground({}, "who is Priya?", [], "m", None, rewriter=rewriter(query)) == ([WEAK], None)
    assert asked == ["who is Priya?"]


def test_weak_evidence_stands_when_the_model_cannot_judge(monkeypatch):
    fake_ground(monkeypatch, {"m": [WEAK]})
    assert followup.ground({}, "m", HISTORY, "m", None, rewriter=rewriter(None)) == ([WEAK], None)


def test_weak_evidence_stands_when_the_step_is_off_or_there_is_no_vault(monkeypatch):
    fake_ground(monkeypatch, {"m": [WEAK]})
    rw = rewriter(followup.NO_TOPIC_QUERY)
    settings_store.set(followup.SETTING, "off")
    assert followup.ground({}, "m", HISTORY, "m", None, rewriter=rw) == ([WEAK], None)
    settings_store.set(followup.SETTING, None)
    monkeypatch.setattr(followup.vault_paths, "resolve_sandbox", lambda persona: None)
    assert followup.ground({}, "m", HISTORY, "m", None, rewriter=rw) == ([WEAK], None)
    assert rw.asked == []


def test_a_hit_that_does_not_say_how_many_words_it_matched_counts_as_strong(monkeypatch):
    fake_ground(monkeypatch, {"m": [HIT]})
    rw = rewriter(followup.NO_TOPIC_QUERY)
    assert followup.ground({}, "m", HISTORY, "m", None, rewriter=rw) == ([HIT], None)
    assert rw.asked == []


# --- rewrite_query: the model call ---


def test_the_rewrite_prompt_carries_the_last_two_exchanges_and_the_message(monkeypatch):
    calls = fake_model(monkeypatch, "Atlas database")
    old = [{"role": "user", "content": "OLDEST"}, {"role": "assistant", "content": "OLDEST reply"}]
    middle = [{"role": "user", "content": "middle q"}, {"role": "assistant", "content": "middle a"}]
    assert followup.rewrite_query(old + middle + HISTORY, "why?", "m", None) == "Atlas database"
    system, user = calls[0]["messages"]
    assert system["role"] == "system" and user["role"] == "user"
    assert "OLDEST" not in user["content"]
    for text in ("middle q", "middle a", "Atlas", "SQLite", "Last message: why?"):
        assert text in user["content"]
    assert calls[0]["max_tokens"] == 4000  # "m" is not a local model: room for thinking


def test_long_messages_are_cut_in_the_rewrite_prompt(monkeypatch):
    calls = fake_model(monkeypatch, "x")
    history = [{"role": "user", "content": "a" * 1000}, {"role": "assistant", "content": "b" * 1000}]
    followup.rewrite_query(history, "why?", "m", None)
    body = calls[0]["messages"][1]["content"]
    assert "a" * 300 in body and "a" * 301 not in body
    assert "b" * 300 in body and "b" * 301 not in body


@pytest.mark.parametrize("reply", ["NONE", "none", "None.", "NONE\nbecause it is small talk"])
def test_none_is_the_models_judgement_that_there_is_no_topic(monkeypatch, reply):
    fake_model(monkeypatch, reply)
    assert followup.rewrite_query(HISTORY, "thanks", "m", None) == followup.NO_TOPIC_QUERY


def test_an_empty_reply_is_no_judgement_at_all(monkeypatch):
    fake_model(monkeypatch, EngineModelError("returned an empty reply"))  # the call itself refuses one
    assert followup.rewrite_query(HISTORY, "thanks", "m", None) is None


def test_a_judgement_of_no_topic_is_not_the_same_as_no_answer():
    assert followup.NO_TOPIC_QUERY is not None and followup.NO_TOPIC_QUERY == ""


def test_a_query_that_merely_starts_with_none_is_kept(monkeypatch):
    fake_model(monkeypatch, "None of the meeting notes mention Priya")
    assert followup.rewrite_query(HISTORY, "and that?", "m", None) == "None of the meeting notes mention Priya"


def test_with_no_earlier_conversation_the_prompt_says_so_instead_of_showing_a_blank(monkeypatch):
    calls = fake_model(monkeypatch, "Priya")
    followup.rewrite_query([], "who is Priya?", "m", None)
    body = calls[0]["messages"][1]["content"]
    assert "(nothing yet: this is the first message)" in body
    assert "Conversation so far:\n\n" not in body


def test_the_query_is_the_first_line_without_quotes(monkeypatch):
    fake_model(monkeypatch, '  "Atlas launch date"\nThis is the query.')
    assert followup.rewrite_query(HISTORY, "when?", "m", None) == "Atlas launch date"


def test_a_failing_model_call_is_no_rewrite_not_a_failed_turn(monkeypatch):
    fake_model(monkeypatch, EngineModelError("connection refused"))
    assert followup.rewrite_query(HISTORY, "why?", "m", None) is None


def test_the_call_uses_the_chats_window_so_a_local_model_is_not_reloaded(monkeypatch):
    calls = fake_model(monkeypatch, "q")
    limits = budget.Budget(prompt_tokens=100000, num_ctx=8192, reply_cap=2048)
    followup.rewrite_query(HISTORY, "why?", "ollama_chat/x", limits)
    assert calls[0]["num_ctx"] == 8192
    assert calls[0]["max_tokens"] == 60  # its own small limit, not the chat's reply cap


def test_a_prompt_that_does_not_fit_the_window_is_not_sent(monkeypatch):
    calls = fake_model(monkeypatch, "q")
    monkeypatch.setattr(budget, "count_tokens", lambda messages, model: 101)
    limits = budget.Budget(prompt_tokens=100, num_ctx=1024, reply_cap=256)
    assert followup.rewrite_query(HISTORY, "why?", "ollama_chat/x", limits) is None
    assert calls == []
    monkeypatch.setattr(budget, "count_tokens", lambda messages, model: 100)
    assert followup.rewrite_query(HISTORY, "why?", "ollama_chat/x", limits) == "q"


def test_a_rewrite_cut_at_the_reply_limit_is_not_searched(monkeypatch):
    fake_model(monkeypatch, "why did we pick SQ", truncated=True)
    assert followup.rewrite_query(HISTORY, "why?", "m", None) is None


def test_a_model_that_spends_the_limit_thinking_is_not_asked_again(monkeypatch):
    calls = fake_model(monkeypatch, ReplyLimitError("reached its reply limit"))
    assert followup.rewrite_query(HISTORY, "why?", "reasoner", None) is None
    assert followup.rewrite_query(HISTORY, "why?", "reasoner", None) is None
    assert len(calls) == 1
    # Only that model: another still gets its rewrite, and so does a plain failure.
    fake_model(monkeypatch, "Atlas")
    assert followup.rewrite_query(HISTORY, "why?", "other", None) == "Atlas"


def test_an_ordinary_failure_does_not_stop_later_rewrites(monkeypatch):
    calls = fake_model(monkeypatch, EngineModelError("connection refused"))
    followup.rewrite_query(HISTORY, "why?", "m", None)
    followup.rewrite_query(HISTORY, "why?", "m", None)
    assert len(calls) == 2


def test_a_cloud_model_gets_room_to_think_and_a_local_one_the_small_limit(monkeypatch):
    calls = fake_model(monkeypatch, "q")
    followup.rewrite_query(HISTORY, "why?", "gemini/gemini-flash-latest", None)
    followup.rewrite_query(HISTORY, "why?", "ollama_chat/x", None)
    followup.rewrite_query(HISTORY, "why?", "ollama/y", None)
    assert [c["max_tokens"] for c in calls] == [4000, 60, 60]
