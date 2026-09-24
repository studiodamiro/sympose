"""Integration tests for sympose.engine.turn.run_turn — proves grounding
results actually reach the model call (not just that each piece works in
isolation) and that session state is threaded through correctly
(docs/decisions/006)."""

import os

import pytest
from helpers import write_persona

from sympose.engine import followup, grounding, prompt, reference, session, turn
from sympose.engine.model import ModelReply


@pytest.fixture(autouse=True)
def no_local_server(monkeypatch):
    """Never ask a real Ollama for a model's window: `run_turn` sizes the
    prompt with it (docs/decisions/015), and these tests must not depend on
    what is installed here."""
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)


@pytest.fixture(autouse=True)
def no_follow_up_rewrite(monkeypatch):
    """The follow-up step (docs/decisions/017) makes its own model call on an
    ungrounded turn with history; these tests count and inspect the chat
    calls, so it is off unless a test turns it on (which also needs a vault:
    whether this machine has one configured must not matter)."""
    monkeypatch.setattr(followup, "enabled", lambda: False)
    monkeypatch.setattr(followup.vault_paths, "resolve_sandbox", lambda persona: ("/vault", ["*"]))
    monkeypatch.setattr(followup, "_CANNOT_REWRITE", set())


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    """A profiles dir with a `samantha` persona; sessions land in
    `<root>/<handle>/sessions/` (docs/decisions/011). Returns the root."""
    base = tmp_path / "profiles"
    # These tests were written for a persona without the Sympose reference library
    # (docs/decisions/022); the library tests turn it on with `_library_persona`.
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(base)


def _fake_grounding_result():
    return {
        "file_name": "Typography.md",
        "rel_path": "Typography.md",
        "match_type": "title",
        "line_no": 1,
        "text": "Some notes about fonts, distinguishably unique text.",
        "title": "Typography",
        "tags": [],
        "index": 1,
    }


def test_grounding_snippet_reaches_the_model_call(sessions_root, monkeypatch):
    monkeypatch.setattr(
        grounding, "ground", lambda profile, msg, max_results=5: [_fake_grounding_result()]
    )
    captured = {}

    def fake_call_model(messages, model=None, **_):
        captured["messages"] = messages
        return ModelReply("a reply", 12)

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "tell me about typography")

    system_message, user_turn = captured["messages"][0]["content"], captured["messages"][-1]["content"]
    assert "Some notes about fonts, distinguishably unique text." in user_turn  # with the question
    assert "distinguishably unique text" not in system_message  # not in the system prompt (ADR 020)
    assert user_turn.endswith("User's message: tell me about typography")
    assert result.reply == "a reply"


def test_new_session_id_generated_when_none_given(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("reply", 12))

    result = turn.run_turn("samantha", "hello")

    assert result.session_id


def test_resumed_session_id_is_preserved_and_history_used(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])

    sid = session.new_session_id()
    session.append_turn("samantha", sid, "first", "first reply")

    captured = {}

    def fake_call_model(messages, model=None, **_):
        captured["messages"] = messages
        return ModelReply("second reply", 12)

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "second", session_id=sid)

    assert result.session_id == sid
    roles_and_content = [(m["role"], m["content"]) for m in captured["messages"]]
    assert ("user", "first") in roles_and_content
    assert ("assistant", "first reply") in roles_and_content


def test_append_turn_is_genuinely_called(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("reply text", 12))

    result = turn.run_turn("samantha", "hello")

    loaded = session.load_session("samantha", result.session_id)
    assert loaded is not None
    assert loaded["turns"][0]["user"] == "hello"
    assert loaded["turns"][0]["assistant"] == "reply text"


def test_resumed_session_file_is_read_only_once_per_turn(sessions_root, monkeypatch):
    """Regression test: `run_turn` loads the session to build history, and
    `append_turn` used to independently reload the same file again to build
    the meta/turns it writes back — doubling the parse cost every turn.
    `run_turn` must now hand its already-loaded session to `append_turn`
    instead of letting it re-read."""
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "first", "first reply")

    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("second reply", 12))

    load_calls = []
    real_load_session = session.load_session

    def counting_load_session(handle, session_id):
        load_calls.append(session_id)
        return real_load_session(handle, session_id)

    monkeypatch.setattr(turn.session, "load_session", counting_load_session)

    turn.run_turn("samantha", "second", session_id=sid)

    assert load_calls == [sid]  # exactly one read for the whole turn


def test_unknown_persona_raises_persona_not_found(sessions_root):
    with pytest.raises(turn.PersonaNotFoundError):
        turn.run_turn("some-typo-handle", "hello")


def test_per_call_model_override_is_passed_through(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    captured = {}

    def fake_call_model(messages, model=None, **_):
        captured["model"] = model
        return ModelReply("reply", 12)

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    turn.run_turn("samantha", "hello", model="ollama_chat/other")

    assert captured["model"] == "ollama_chat/other"


def _capture_model(monkeypatch):
    captured = {}

    def fake_call_model(messages, model=None, **_):
        captured["model"] = model
        return ModelReply("reply", 12)

    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)
    return captured


def test_run_turn_uses_the_personas_own_model_when_none_is_given(
    sessions_root, monkeypatch
):
    monkeypatch.setattr(
        turn.profile_mod,
        "resolve_profile",
        lambda h: {"handle": h, "name": "Dev", "vault_folders": ["*"], "model": "ollama_chat/dev-pick"},
    )
    captured = _capture_model(monkeypatch)

    turn.run_turn("dev", "hello")

    assert captured["model"] == "ollama_chat/dev-pick"


def test_run_turn_explicit_model_beats_the_personas_model(sessions_root, monkeypatch):
    monkeypatch.setattr(
        turn.profile_mod,
        "resolve_profile",
        lambda h: {"handle": h, "name": "Dev", "vault_folders": ["*"], "model": "ollama_chat/dev-pick"},
    )
    captured = _capture_model(monkeypatch)

    turn.run_turn("dev", "hello", model="anthropic/claude-sonnet-5")

    assert captured["model"] == "anthropic/claude-sonnet-5"


def test_ttft_and_model_are_recorded_on_the_turn_and_the_session(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(
        turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("hi", 734)
    )

    result = turn.run_turn("samantha", "hello", model="ollama_chat/some-model")

    assert result.ttft_ms == 734
    assert result.model == "ollama_chat/some-model"
    record = session.load_session("samantha", result.session_id)["turns"][0]
    assert record["ttft_ms"] == 734
    assert record["model"] == "ollama_chat/some-model"


def test_the_recorded_model_is_the_one_that_actually_ran(sessions_root, monkeypatch):
    """Not the explicit argument (there is none here): the resolved
    persona/setting/default model, which is what a later latency comparison
    across models needs."""
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    seen = {}

    def fake_call_model(messages, model=None, **_):
        seen["model"] = model
        return ModelReply("hi", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "hello")

    assert result.model == seen["model"] == turn.model_mod.DEFAULT_LOCAL_MODEL


def test_a_session_written_before_ttft_existed_still_loads_and_continues(sessions_root):
    """Older turn records lack `ttft_ms`/`model`; nothing may depend on them."""
    import json
    import os

    sid = "20260101T000000-old"
    path = session.session_path("samantha", sid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "meta", "session_id": sid, "handle": "samantha", "title": "t",
                            "created_at": "x", "updated_at": "x", "turns_count": 1}) + "\n")
        f.write(json.dumps({"type": "turn", "timestamp": "x", "user": "old q", "assistant": "old a"}) + "\n")

    loaded = session.load_session("samantha", sid)
    assert session.history_as_messages(loaded)[0]["content"] == "old q"

    session.append_turn("samantha", sid, "new q", "new a", ttft_ms=90, model="m")
    turns = session.load_session("samantha", sid)["turns"]
    assert "ttft_ms" not in turns[0] and turns[1]["ttft_ms"] == 90


# -- the prompt is sized to the model's window (docs/decisions/015) --


def _capture_call(monkeypatch):
    """Records every model call's full arguments."""
    calls = []

    def fake_call_model(messages, model=None, **limits):
        calls.append({"messages": messages, "model": model, **limits})
        return ModelReply("reply", 12)

    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)
    return calls


def test_a_local_model_gets_its_own_window_and_a_reply_cap(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 8192)
    calls = _capture_call(monkeypatch)
    turn.run_turn("samantha", "hello")
    assert calls[0]["num_ctx"] == 8192 and calls[0]["max_tokens"] == 2048


def test_a_local_model_with_an_unknown_maximum_gets_ollamas_own_default(sessions_root, monkeypatch):
    calls = _capture_call(monkeypatch)  # the fixture makes the lookup return nothing
    turn.run_turn("samantha", "hello")
    assert calls[0]["num_ctx"] == 4096 and calls[0]["max_tokens"] == 1024


def test_a_huge_local_maximum_is_capped_and_a_users_setting_is_kept(sessions_root, monkeypatch):
    from sympose import settings_store

    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 131072)
    calls = _capture_call(monkeypatch)
    turn.run_turn("samantha", "hello")
    settings_store.set("context_window", 16384)
    turn.run_turn("samantha", "hello again", model="ollama_chat/another")
    assert [c["num_ctx"] for c in calls] == [32768, 16384]


def test_a_cloud_model_is_sent_no_window_and_no_reply_cap(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 128000)
    calls = _capture_call(monkeypatch)
    turn.run_turn("samantha", "hello", model="anthropic/some-model")
    assert calls[0]["num_ctx"] is None and calls[0]["max_tokens"] is None


def test_a_model_with_no_known_window_is_not_trimmed(sessions_root, monkeypatch):
    calls = _capture_call(monkeypatch)
    sid = None
    for i in range(3):
        sid = turn.run_turn(
            "samantha", f"q{i} " + "word " * 400, session_id=sid, model="unknown/model"
        ).session_id
    result = turn.run_turn("samantha", "last", session_id=sid, model="unknown/model")
    assert result.history_dropped == 0
    assert len(calls[-1]["messages"]) == 1 + 2 * 3 + 1


def test_a_long_chat_drops_the_oldest_turns_but_never_the_soul_or_the_record(
    sessions_root, monkeypatch, tmp_path
):
    from sympose import settings_store

    settings_store.set("context_window", 2048)  # small on purpose: trimming starts early
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(
        turn.model_mod,
        "call_model",
        lambda messages, model=None, **limits: (
            calls.append({"messages": messages, **limits}) or ModelReply("answer " * 250, 12)
        ),
    )
    sid, result = None, None
    for i in range(6):
        result = turn.run_turn("samantha", f"question {i}", session_id=sid)
        sid = result.session_id

    sent = calls[-1]["messages"]
    assert prompt.GROUNDING_RULE in sent[0]["content"]  # the engine rules are never cut
    assert sent[-1]["content"].endswith("User's message: question 5")
    pairs_sent = (len(sent) - 2) // 2
    assert result.history_dropped > 0
    assert result.history_dropped == 5 - pairs_sent  # five earlier turns, the rest are sent
    assert len(session.load_session("samantha", sid)["turns"]) == 6  # nothing is deleted from the record


def test_a_window_too_small_for_the_soul_fails_before_calling_the_model(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    calls = _capture_call(monkeypatch)
    with pytest.raises(turn.budget.ContextTooSmallError):
        turn.run_turn("samantha", "word " * 3000)
    assert calls == []
    directory = session.sessions_dir("samantha")
    assert not os.path.isdir(directory) or os.listdir(directory) == []  # no turn was recorded


def test_the_passages_reported_are_the_ones_the_model_actually_saw(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    hits = [
        {**_fake_grounding_result(), "title": f"Note{i}", "rel_path": f"Note{i}.md", "index": i + 1,
         "text": ("filler words for the passage " * 40) + f"unique{i}"}
        for i in range(5)
    ]
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: list(hits))
    calls = []
    monkeypatch.setattr(
        turn.model_mod,
        "call_model",
        lambda messages, model=None, **limits: calls.append(messages) or ModelReply("ok", 12),
    )
    result = turn.run_turn("samantha", "hello")
    system = calls[0][-1]["content"]
    assert 0 < len(result.grounding) < 5  # the lowest-scoring passages went first
    assert result.grounding == hits[: len(result.grounding)]
    for i in range(5):
        assert (f"unique{i}" in system) == (i < len(result.grounding))


def test_when_every_passage_is_left_out_the_prompt_does_not_claim_nothing_matched(
    sessions_root, monkeypatch
):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    big = {**_fake_grounding_result(), "text": "filler words for the passage " * 200}
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [big])
    calls = []
    monkeypatch.setattr(
        turn.model_mod, "call_model",
        lambda messages, model=None, **limits: calls.append(messages) or ModelReply("ok", 12),
    )
    result = turn.run_turn("samantha", "hello")
    system = calls[0][-1]["content"]
    assert result.grounding == []
    assert prompt.NO_NOTES not in system
    assert "could not be included" in system


def test_a_reply_that_hit_the_reply_limit_is_reported_on_the_result(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(
        turn.model_mod, "call_model",
        lambda messages, model=None, **limits: ModelReply("half a sen", 12, truncated=True),
    )
    assert turn.run_turn("samantha", "hello").truncated is True


def test_a_users_reply_limit_reaches_the_model_call(sessions_root, monkeypatch):
    from sympose import settings_store

    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 8192)
    settings_store.set("reply_limit", 500)
    calls = _capture_call(monkeypatch)
    turn.run_turn("samantha", "hello")
    assert calls[0]["max_tokens"] == 500


def _first_turn_then_follow_up(monkeypatch, rewrite_reply: str, answers: dict[str, list]):
    """Runs a first turn, then the bare follow-up "why did we pick it?" with the
    retriever answering only the queries in `answers`. Returns the follow-up's
    result and every model call made during it, chat call last."""
    monkeypatch.setattr(followup, "enabled", lambda: True)
    monkeypatch.setattr(
        grounding, "ground", lambda profile, msg, max_results=5: list(answers.get(msg, []))
    )
    calls: list[list[dict]] = []

    def call_model(messages, model=None, **limits):
        calls.append(messages)
        is_rewrite = "standalone search query" in messages[0]["content"]
        return ModelReply(rewrite_reply if is_rewrite else "a chat reply", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    first = turn.run_turn("samantha", "what did we decide about Atlas?")
    calls.clear()
    return turn.run_turn("samantha", "why did we pick it?", first.session_id), calls


def test_a_follow_up_is_grounded_on_its_rewritten_query(sessions_root, monkeypatch):
    hit = _fake_grounding_result()
    result, calls = _first_turn_then_follow_up(
        monkeypatch, "why SQLite for Atlas", {"why SQLite for Atlas": [hit]}
    )
    assert len(calls) == 2  # the rewrite, then the chat
    chat = calls[1]
    assert "distinguishably unique text" in chat[-1]["content"]  # the note reached the model
    assert chat[-1]["content"].endswith("User's message: why did we pick it?")  # the user's own words
    assert all("why SQLite for Atlas" not in m["content"] for m in chat)  # the rewrite is not shown to it
    assert result.searched == "why SQLite for Atlas"
    assert result.grounding == [hit]


def test_the_rewrite_is_not_saved_as_a_turn(sessions_root, monkeypatch):
    result, _ = _first_turn_then_follow_up(
        monkeypatch, "why SQLite for Atlas", {"why SQLite for Atlas": [_fake_grounding_result()]}
    )
    turns = session.load_session("samantha", result.session_id)["turns"]
    assert [t["user"] for t in turns] == ["what did we decide about Atlas?", "why did we pick it?"]
    assert "why SQLite for Atlas" not in str(turns)


def test_a_follow_up_whose_rewrite_finds_nothing_is_an_ordinary_ungrounded_turn(sessions_root, monkeypatch):
    result, calls = _first_turn_then_follow_up(monkeypatch, "NONE", {})
    assert len(calls) == 2
    assert result.searched is None and result.grounding == []
    assert prompt.NO_NOTES in calls[1][-1]["content"]


def test_a_rewritten_query_is_not_reported_when_every_passage_was_left_out_for_size(
    sessions_root, monkeypatch
):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    big = {**_fake_grounding_result(), "text": "filler words for the passage " * 200}
    result, _ = _first_turn_then_follow_up(monkeypatch, "why SQLite for Atlas", {"why SQLite for Atlas": [big]})
    assert result.grounding == [] and result.searched is None


def test_the_rewrite_call_runs_in_the_same_window_as_the_chat_call(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 8192)
    monkeypatch.setattr(followup, "enabled", lambda: True)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    windows = []

    def call_model(messages, model=None, **limits):
        windows.append(limits.get("num_ctx"))
        return ModelReply("NONE", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    first = turn.run_turn("samantha", "hello", model="ollama_chat/x")
    windows.clear()
    turn.run_turn("samantha", "thanks", first.session_id, model="ollama_chat/x")
    assert windows == [8192, 8192]  # the rewrite, then the chat: no reload between them


def test_the_result_reports_the_conversations_size_for_the_meter(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)  # prompt budget: 2048 minus a quarter kept for the reply
    monkeypatch.setattr(turn.budget, "count_tokens", lambda messages, model: sum(len(m["content"].split()) for m in messages))
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    sent = []

    def call_model(messages, model=None, **limits):
        sent.append(messages)
        return ModelReply("one two three", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    result = turn.run_turn("samantha", "hello there")
    prompt_words = sum(len(m["content"].split()) for m in sent[0])
    assert result.context_limit == 1536
    assert result.context_used == prompt_words + 3  # what was sent, plus the reply it produced


def test_no_meter_figures_when_the_models_window_is_unknown(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **limits: ModelReply("ok", 5))
    result = turn.run_turn("samantha", "hi", model="someprovider/unknown-model")
    assert result.context_used is None and result.context_limit is None


# -- the Sympose reference library (docs/decisions/022) --


def _reference_hit(text="Not yet. A new conversation starts without the last one."):
    return {
        "rel_path": "Sympose reference/Not built yet.md", "title": "Not built yet", "heading": "Memory",
        "text": text, "source": "sympose", "matched": 2, "index": 1,
    }


def _library_persona(sessions_root):
    write_persona(__import__("pathlib").Path(sessions_root), "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: true\n")


def test_the_reference_passages_come_first_and_travel_in_their_own_block(sessions_root, monkeypatch):
    _library_persona(sessions_root)
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [_fake_grounding_result()])
    monkeypatch.setattr(reference, "ground", lambda persona, msg: [_reference_hit()])

    result = turn.run_turn("samantha", "do you remember last time?")

    assert [h.get("source") for h in result.grounding] == ["sympose", None]
    last = calls[0]["messages"][-1]["content"]
    assert last.index("Notes found in the vault") < last.index(prompt.REFERENCE_LABEL)
    assert "A new conversation starts without the last one." in last


def test_a_persona_without_the_library_never_searches_it(sessions_root, monkeypatch):
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    calls = _capture_call(monkeypatch)

    result = turn.run_turn("samantha", "who made Sympose?")  # the fixture persona has no flag

    assert result.grounding == []
    assert prompt.REFERENCE_LABEL not in calls[0]["messages"][-1]["content"]


def test_the_rewritten_query_is_reported_only_for_the_vaults_passages(sessions_root, monkeypatch):
    _library_persona(sessions_root)
    monkeypatch.setattr(reference, "ground", lambda persona, msg: [_reference_hit()])
    result, _ = _first_turn_then_follow_up(
        monkeypatch, "why SQLite for Atlas", {"why SQLite for Atlas": [_fake_grounding_result()]}
    )
    assert result.searched == "why SQLite for Atlas"
    assert [h.get("source") for h in result.grounding] == ["sympose", None]


def test_when_the_prompt_does_not_fit_the_vaults_passages_go_before_the_reference(sessions_root, monkeypatch):
    from sympose import settings_store

    _library_persona(sessions_root)
    settings_store.set("context_window", 2048)
    big = {**_fake_grounding_result(), "text": _text_of_tokens(_free_tokens() * 2)}  # too big to fit even alone
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [big, {**big, "title": "Other"}])
    monkeypatch.setattr(reference, "ground", lambda persona, msg: [_reference_hit()])

    result = turn.run_turn("samantha", "hello")

    assert result.grounding and result.grounding[0].get("source") == "sympose"  # kept
    assert [h.get("source") for h in result.grounding] == ["sympose"]  # both vault passages went, the reference stayed
    last = calls[0]["messages"][-1]["content"]
    assert "Notes in the vault matched this message, but they could not be included" in last  # the vault says so
    assert "Sympose reference passages matched" not in last  # and the reference does not
    assert "A new conversation starts without the last one." in last
    assert prompt.NO_REFERENCE not in last


def _free_tokens(persona_handle="samantha", model="ollama_chat/gemma2:9b", window=2048):
    """How many tokens of the prompt budget are left once the persona's own prompt and an
    empty turn are in, so the trimming tests size their passages from the prompt as it is
    now and do not break each time its wording changes."""
    from sympose.engine import budget
    from sympose.profile import resolve_profile

    messages = prompt.build_messages(resolve_profile(persona_handle), [], [], "hello")
    return window - budget.reply_reserve(window) - budget.count_tokens(messages, model)


def _text_of_tokens(tokens: int, model="ollama_chat/gemma2:9b") -> str:
    from sympose.engine import budget

    unit = "filler words for the passage "
    per_unit = budget.count_tokens([{"role": "user", "content": unit * 10}], model) / 10
    return unit * max(1, int(tokens / per_unit))


def test_vault_passages_left_out_are_counted_while_the_reference_stays(sessions_root, monkeypatch):
    from sympose import settings_store

    _library_persona(sessions_root)
    settings_store.set("context_window", 2048)
    size = int(_free_tokens() * 0.45)  # two of the three fit, three do not
    vault = [{**_fake_grounding_result(), "title": f"V{i}", "text": _text_of_tokens(size)} for i in range(3)]
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: list(vault))
    monkeypatch.setattr(reference, "ground", lambda persona, msg: [_reference_hit()])

    result = turn.run_turn("samantha", "hello")

    assert [h.get("source") for h in result.grounding] == ["sympose", None, None]
    last = calls[0]["messages"][-1]["content"]
    assert "(1 more matching passages were left out" in last
    assert "more reference passages were left out" not in last


def test_reference_passages_left_out_are_counted_apart_from_the_vaults(sessions_root, monkeypatch):
    from sympose import settings_store

    _library_persona(sessions_root)
    settings_store.set("context_window", 2048)
    text = _text_of_tokens(int(_free_tokens() * 0.7))  # one fits, two do not
    two = [_reference_hit(text), {**_reference_hit(text), "title": "Other"}]
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(reference, "ground", lambda persona, msg: list(two))

    result = turn.run_turn("samantha", "hello")

    assert [h.get("source") for h in result.grounding] == ["sympose"]
    last = calls[0]["messages"][-1]["content"]
    assert "(1 more reference passages were left out" in last
    assert prompt.NO_NOTES in last  # the vault had nothing, and is not said to have had something
    assert "Notes in the vault matched" not in last


def test_the_two_sources_take_turns_so_neither_is_dropped_wholesale():
    ref = [{"source": "sympose", "n": i} for i in range(3)]
    vault = [{"n": i} for i in range(2)]

    merged = turn._interleave(ref, vault)

    assert [(h.get("source"), h["n"]) for h in merged] == [
        ("sympose", 0), (None, 0), ("sympose", 1), (None, 1), ("sympose", 2),
    ]
    assert turn._interleave([], vault) == vault and turn._interleave(ref, []) == ref


def test_under_a_tight_window_the_best_vault_passage_outlasts_the_weaker_reference_ones(sessions_root, monkeypatch):
    from sympose import settings_store

    _library_persona(sessions_root)
    settings_store.set("context_window", 2048)
    text = _text_of_tokens(int(_free_tokens() * 0.4))  # two of the four fit
    refs = [{**_reference_hit(text), "title": f"R{i}"} for i in range(2)]
    vault = [{**_fake_grounding_result(), "title": f"V{i}", "text": text} for i in range(2)]
    _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: list(vault))
    monkeypatch.setattr(reference, "ground", lambda persona, msg: list(refs))

    result = turn.run_turn("samantha", "hello")

    assert [(h.get("source"), h["title"]) for h in result.grounding] == [("sympose", "R0"), (None, "V0")]


def test_the_roster_is_read_once_per_turn_not_once_per_trimming_attempt(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    reads = []
    monkeypatch.setattr(turn.profile_mod, "reference_persona_names", lambda: reads.append(1) or [])
    monkeypatch.setattr(prompt, "reference_persona_names", lambda: reads.append(1) or [])
    _capture_call(monkeypatch)
    monkeypatch.setattr(
        grounding, "ground",
        lambda profile, msg, max_results=5: [{**_fake_grounding_result(), "text": "filler words " * 200}] * 3,
    )

    turn.run_turn("samantha", "hello")

    assert len(reads) == 1  # although three passages were dropped one attempt at a time



# -- recaps of earlier conversations (docs/decisions/023) --


def _put_recap(session_id, text, handle="samantha"):
    session.append_turn(handle, session_id, "question", "answer")  # the session the recap is of
    os.makedirs(session.recaps_dir(handle), exist_ok=True)
    with open(os.path.join(session.recaps_dir(handle), f"{session_id}.md"), "w", encoding="utf-8") as f:
        f.write(f"<!-- turns: 2 -->\n{text}\n")


def test_the_recaps_of_earlier_conversations_travel_with_the_message(sessions_root, monkeypatch):
    _put_recap("20260923T090000-bbbbbbbb", "Was planning a trip to Lisbon.")
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "where did we leave off?")

    last = calls[0]["messages"][-1]["content"]
    assert "- Last conversation (2026-09-23): Was planning a trip to Lisbon." in last
    assert last.endswith("User's message: where did we leave off?")
    assert "Lisbon" not in calls[0]["messages"][0]["content"]


def test_the_conversation_being_run_is_not_recapped_into_itself(sessions_root, monkeypatch):
    _put_recap("20260923T090000-bbbbbbbb", "Was planning a trip to Lisbon.")
    _put_recap("20260924T090000-aaaaaaaa", "This very conversation, earlier.")
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "hello", session_id="20260924T090000-aaaaaaaa")

    last = calls[0]["messages"][-1]["content"]
    assert "Lisbon" in last and "This very conversation" not in last


def test_with_no_recaps_the_turn_says_nothing_about_them(sessions_root, monkeypatch):
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "hello")

    assert prompt.RECAPS_LABEL not in calls[0]["messages"][-1]["content"]


def test_the_knob_keeps_recaps_out_of_the_prompt(sessions_root, monkeypatch):
    from sympose import settings_store

    _put_recap("20260923T090000-bbbbbbbb", "Was planning a trip to Lisbon.")
    settings_store.set("session_recaps", False)
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "hello")

    assert "Lisbon" not in calls[0]["messages"][-1]["content"]


def test_when_the_window_is_short_the_recaps_go_first_and_the_turn_says_so(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    _put_recap("20260923T090000-bbbbbbbb", _text_of_tokens(300))  # read back at 800 characters, about 170 tokens
    _put_recap("20260922T090000-cccccccc", _text_of_tokens(300))
    big = {**_fake_grounding_result(), "text": _text_of_tokens(_free_tokens() - 250)}  # room for one recap, not two
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [big])

    result = turn.run_turn("samantha", "hello")

    last = calls[0]["messages"][-1]["content"]
    assert "2026-09-23" in last and "2026-09-22" not in last  # the older recap went, the newer stayed
    assert "(1 more recaps were left out to fit the context window.)" in last
    assert result.grounding == [big]  # the note passage was not sacrificed for it


def test_when_no_recap_fits_the_turn_does_not_claim_there_were_none(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 2048)
    _put_recap("20260923T090000-bbbbbbbb", _text_of_tokens(300))
    big = {**_fake_grounding_result(), "text": _text_of_tokens(_free_tokens() - 100)}  # room for no recap
    calls = _capture_call(monkeypatch)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [big])

    result = turn.run_turn("samantha", "hello")

    last = calls[0]["messages"][-1]["content"]
    assert result.grounding == [big]
    assert "Recaps of earlier conversations exist but could not be included" in last
    assert prompt.RECAPS_LABEL not in last


def test_recaps_reach_the_prompt_of_a_model_whose_window_is_unknown_too(sessions_root, monkeypatch):
    _put_recap("20260923T090000-bbbbbbbb", "Was planning a trip to Lisbon.")
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "hello", model="someprovider/unknown-model")

    assert "Was planning a trip to Lisbon." in calls[0]["messages"][-1]["content"]


def test_a_turn_waits_for_the_recap_being_written_at_launch_before_reading_recaps(sessions_root, monkeypatch):
    waited = []

    def finish_writing(handle, *args):
        waited.append(handle)
        _put_recap("20260923T090000-bbbbbbbb", "Was planning a trip to Lisbon.")  # done by the time it returns

    monkeypatch.setattr(turn.recap_refresh, "wait_for_refresh", finish_writing)
    calls = _capture_call(monkeypatch)

    turn.run_turn("samantha", "where did we leave off?")

    assert waited == ["samantha"]
    assert "Was planning a trip to Lisbon." in calls[0]["messages"][-1]["content"]
