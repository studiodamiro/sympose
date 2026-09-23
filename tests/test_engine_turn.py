"""Integration tests for sympose.engine.turn.run_turn — proves grounding
results actually reach the model call (not just that each piece works in
isolation) and that session state is threaded through correctly
(docs/decisions/006)."""

from helpers import write_persona
import pytest

from sympose.engine import session, turn


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
        "snippet": "Some notes about fonts, distinguishably unique text.",
        "title": "Typography",
        "tags": [],
        "index": 1,
    }


def test_grounding_snippet_reaches_the_model_call(sessions_root, monkeypatch):
    monkeypatch.setattr(
        turn.grounding, "ground", lambda profile, msg, max_results=5: [_fake_grounding_result()]
    )
    captured = {}

    def fake_call_model(messages, model=None):
        captured["messages"] = messages
        return "a reply"

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "tell me about typography")

    system_message = captured["messages"][0]["content"]
    assert "Some notes about fonts, distinguishably unique text." in system_message
    assert result.reply == "a reply"


def test_new_session_id_generated_when_none_given(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None: "reply")

    result = turn.run_turn("samantha", "hello")

    assert result.session_id


def test_resumed_session_id_is_preserved_and_history_used(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])

    sid = session.new_session_id()
    session.append_turn("samantha", sid, "first", "first reply")

    captured = {}

    def fake_call_model(messages, model=None):
        captured["messages"] = messages
        return "second reply"

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    result = turn.run_turn("samantha", "second", session_id=sid)

    assert result.session_id == sid
    roles_and_content = [(m["role"], m["content"]) for m in captured["messages"]]
    assert ("user", "first") in roles_and_content
    assert ("assistant", "first reply") in roles_and_content


def test_append_turn_is_genuinely_called(sessions_root, monkeypatch):
    monkeypatch.setattr(turn.grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None: "reply text")

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
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None: "second reply")

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

    def fake_call_model(messages, model=None):
        captured["model"] = model
        return "reply"

    monkeypatch.setattr(turn.model_mod, "call_model", fake_call_model)

    turn.run_turn("samantha", "hello", model="ollama_chat/other")

    assert captured["model"] == "ollama_chat/other"


def _capture_model(monkeypatch):
    captured = {}

    def fake_call_model(messages, model=None):
        captured["model"] = model
        return "reply"

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
