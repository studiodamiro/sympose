"""Integration tests for sympose.engine.turn.run_turn — proves grounding
results actually reach the model call (not just that each piece works in
isolation) and that session state is threaded through correctly
(docs/decisions/006)."""

import os

import pytest
from helpers import write_persona

from sympose.engine import session, turn
from sympose.engine.model import ModelReply


@pytest.fixture(autouse=True)
def no_local_server(monkeypatch):
    """Never ask a real Ollama for a model's window: `run_turn` sizes the
    prompt with it (docs/decisions/015), and these tests must not depend on
    what is installed here."""
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    """A profiles dir with a `samantha` persona; sessions land in
    `<root>/<handle>/sessions/` (docs/decisions/011). Returns the root."""
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
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
        turn.grounding, "ground", lambda profile, msg, max_results=5: [_fake_grounding_result()]
    )
    captured = {}

    def fake_call_model(messages, model=None, **_):
        captured["messages"] = messages
        return ModelReply("a reply", 12)

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "tell me about typography")

    system_message = captured["messages"][0]["content"]
    assert "Some notes about fonts, distinguishably unique text." in system_message
    assert result.reply == "a reply"


def test_new_session_id_generated_when_none_given(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("reply", 12))

    result = turn.run_turn("samantha", "hello")

    assert result.session_id


def test_resumed_session_id_is_preserved_and_history_used(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])

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
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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

    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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

    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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

    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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
    from sympose.engine import prompt

    settings_store.set("context_window", 1024)  # small on purpose: trimming starts early
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
    assert prompt._GROUNDING_INSTRUCTION in sent[0]["content"]  # the engine rules are never cut
    assert sent[-1] == {"role": "user", "content": "question 5"}
    pairs_sent = (len(sent) - 2) // 2
    assert result.history_dropped > 0
    assert result.history_dropped == 5 - pairs_sent  # five earlier turns, the rest are sent
    assert len(session.load_session("samantha", sid)["turns"]) == 6  # nothing is deleted from the record


def test_a_window_too_small_for_the_soul_fails_before_calling_the_model(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 1024)
    calls = _capture_call(monkeypatch)
    with pytest.raises(turn.budget.ContextTooSmallError):
        turn.run_turn("samantha", "word " * 3000)
    assert calls == []
    directory = session.sessions_dir("samantha")
    assert not os.path.isdir(directory) or os.listdir(directory) == []  # no turn was recorded


def test_the_passages_reported_are_the_ones_the_model_actually_saw(sessions_root, monkeypatch):
    from sympose import settings_store

    settings_store.set("context_window", 1024)
    hits = [
        {**_fake_grounding_result(), "title": f"Note{i}", "rel_path": f"Note{i}.md", "index": i + 1,
         "text": ("filler words for the passage " * 40) + f"unique{i}"}
        for i in range(5)
    ]
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: list(hits))
    calls = []
    monkeypatch.setattr(
        turn.model_mod,
        "call_model",
        lambda messages, model=None, **limits: calls.append(messages) or ModelReply("ok", 12),
    )
    result = turn.run_turn("samantha", "hello")
    system = calls[0][0]["content"]
    assert 0 < len(result.grounding) < 5  # the lowest-scoring passages went first
    assert result.grounding == hits[: len(result.grounding)]
    for i in range(5):
        assert (f"unique{i}" in system) == (i < len(result.grounding))


def test_when_every_passage_is_left_out_the_prompt_does_not_claim_nothing_matched(
    sessions_root, monkeypatch
):
    from sympose import settings_store

    settings_store.set("context_window", 1024)
    big = {**_fake_grounding_result(), "text": "filler words for the passage " * 200}
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [big])
    calls = []
    monkeypatch.setattr(
        turn.model_mod, "call_model",
        lambda messages, model=None, **limits: calls.append(messages) or ModelReply("ok", 12),
    )
    result = turn.run_turn("samantha", "hello")
    system = calls[0][0]["content"]
    assert result.grounding == []
    assert "No vault notes matched" not in system
    assert "could not be included" in system


def test_a_reply_that_hit_the_reply_limit_is_reported_on_the_result(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
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
