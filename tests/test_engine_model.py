"""Tests for sympose.engine.model — model resolution and the litellm call
itself, fully mocked (no network calls) (docs/decisions/007)."""

import pytest

from sympose.engine import model


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _EmptyChoicesResponse:
    choices: list = []


def test_resolve_model_defaults_to_local(settings_file):
    assert model.resolve_model() == model.DEFAULT_LOCAL_MODEL
    assert model.DEFAULT_LOCAL_MODEL.startswith("ollama_chat/")


def test_resolve_model_honors_settings_override(settings_file):
    from sympose import settings_store

    settings_store.set("chat_model", "anthropic/claude-sonnet")
    assert model.resolve_model() == "anthropic/claude-sonnet"


def test_call_model_is_non_streaming_and_extracts_content(settings_file, monkeypatch):
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["model"] = model
        captured["messages"] = messages
        captured["stream"] = stream
        captured["timeout"] = timeout
        return _FakeResponse("hello from the model")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    reply = model.call_model([{"role": "user", "content": "hi"}])

    assert reply == "hello from the model"
    assert captured["stream"] is False
    assert captured["model"] == model.DEFAULT_LOCAL_MODEL


def test_call_model_passes_a_finite_timeout(settings_file, monkeypatch):
    """Regression test: `litellm.completion` was called with no timeout —
    combined with the CLI's single global `turn_lock` (docs/decisions/006),
    a genuinely hung request (stalled Ollama process, a network partition)
    would wedge every future message behind it forever, with no error and
    no way out short of killing the process."""
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["timeout"] = timeout
        return _FakeResponse("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}])

    assert isinstance(captured["timeout"], (int, float))
    assert captured["timeout"] > 0


def test_call_model_uses_explicit_model_override(settings_file, monkeypatch):
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["model"] = model
        return _FakeResponse("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}], model="ollama_chat/other")

    assert captured["model"] == "ollama_chat/other"


def test_call_model_failure_raises_engine_model_error(settings_file, monkeypatch):
    def failing_completion(model, messages, stream, timeout):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(model.litellm, "completion", failing_completion)

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_call_model_timeout_raises_engine_model_error(settings_file, monkeypatch):
    def timing_out_completion(model, messages, stream, timeout):
        raise TimeoutError("request timed out")

    monkeypatch.setattr(model.litellm, "completion", timing_out_completion)

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_call_model_empty_choices_raises_engine_model_error_not_a_crash(settings_file, monkeypatch):
    """Regression test: `response.choices[0]` used to be evaluated outside
    the try/except wrapping the call, so a 200 response with no choices
    (or a null `.content`) raised a raw IndexError/AttributeError instead
    of the friendly EngineModelError every other failure path produces."""
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda model, messages, stream, timeout: _EmptyChoicesResponse(),
    )

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_call_model_null_content_raises_engine_model_error_not_a_crash(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: _FakeResponse(None)
    )

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])
