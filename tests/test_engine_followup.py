"""Tests for sympose.engine.followup (docs/decisions/017): when a follow-up is
rewritten, what the rewrite is shown, and that every way the step can fail
leaves the turn grounded exactly as before. Retrieval on the fixture vault is
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
    assert calls[0]["max_tokens"] == 60


def test_long_messages_are_cut_in_the_rewrite_prompt(monkeypatch):
    calls = fake_model(monkeypatch, "x")
    history = [{"role": "user", "content": "a" * 1000}, {"role": "assistant", "content": "b" * 1000}]
    followup.rewrite_query(history, "why?", "m", None)
    body = calls[0]["messages"][1]["content"]
    assert "a" * 300 in body and "a" * 301 not in body
    assert "b" * 300 in body and "b" * 301 not in body


@pytest.mark.parametrize("reply", ["NONE", "none", "None.", "NONE\nbecause it is small talk", "", "   \n"])
def test_a_reply_with_no_query_in_it_is_no_rewrite(monkeypatch, reply):
    if not reply.strip():  # the model call itself refuses an empty reply
        fake_model(monkeypatch, EngineModelError("returned an empty reply"))
    else:
        fake_model(monkeypatch, reply)
    assert followup.rewrite_query(HISTORY, "thanks", "m", None) is None


def test_a_query_that_merely_starts_with_none_is_kept(monkeypatch):
    fake_model(monkeypatch, "None of the meeting notes mention Priya")
    assert followup.rewrite_query(HISTORY, "and that?", "m", None) == "None of the meeting notes mention Priya"


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
