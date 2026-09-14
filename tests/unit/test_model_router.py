"""
Unit tests for sympose.model_router's Ollama warm-check/warm-up helpers
and the ADR-122 SIMPLE-tier classifier/decision function.
"""

import json


from sympose import model_router


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestIsOllamaModelWarm:
    def test_true_when_model_is_in_the_loaded_list(self, monkeypatch):
        monkeypatch.setattr(
            model_router.urllib.request,
            "urlopen",
            lambda *a, **k: _FakeResponse({"models": [{"name": "gemma2:9b"}]}),
        )
        assert model_router.is_ollama_model_warm("gemma2:9b") is True

    def test_false_when_model_is_not_in_the_loaded_list(self, monkeypatch):
        monkeypatch.setattr(
            model_router.urllib.request,
            "urlopen",
            lambda *a, **k: _FakeResponse({"models": [{"name": "qwen2.5:14b"}]}),
        )
        assert model_router.is_ollama_model_warm("gemma2:9b") is False

    def test_false_when_ollama_is_unreachable(self, monkeypatch):
        def _raise(*a, **k):
            raise OSError("connection refused")

        monkeypatch.setattr(model_router.urllib.request, "urlopen", _raise)
        assert model_router.is_ollama_model_warm("gemma2:9b") is False

    def test_false_on_malformed_response(self, monkeypatch):
        class _BadResponse(_FakeResponse):
            def read(self) -> bytes:
                return b"not json"

        monkeypatch.setattr(
            model_router.urllib.request, "urlopen", lambda *a, **k: _BadResponse({})
        )
        assert model_router.is_ollama_model_warm("gemma2:9b") is False


class TestWarmOllamaModel:
    def test_sends_a_minimal_throwaway_request(self, monkeypatch):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse({})

        monkeypatch.setattr(model_router.urllib.request, "urlopen", fake_urlopen)

        model_router.warm_ollama_model("gemma2:9b", keep_alive="30m", timeout=5.0)

        assert captured["url"] == "http://localhost:11434/api/generate"
        assert captured["body"]["model"] == "gemma2:9b"
        assert captured["body"]["options"]["num_predict"] == 1
        assert captured["body"]["keep_alive"] == "30m"
        assert captured["timeout"] == 5.0

    def test_omits_keep_alive_when_not_given(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            model_router.urllib.request,
            "urlopen",
            lambda req, timeout=None: (
                captured.update(body=json.loads(req.data.decode("utf-8")))
                or _FakeResponse({})
            ),
        )

        model_router.warm_ollama_model("gemma2:9b")

        assert "keep_alive" not in captured["body"]

    def test_never_raises_even_if_ollama_is_unreachable(self, monkeypatch):
        def _raise(*a, **k):
            raise OSError("connection refused")

        monkeypatch.setattr(model_router.urllib.request, "urlopen", _raise)

        # Must not raise — this runs on a background thread with nothing to
        # catch it (see compactor.run_hygiene_task).
        model_router.warm_ollama_model("gemma2:9b")


class TestIsSimpleMessage:
    def test_true_for_a_short_greeting(self):
        assert model_router.is_simple_message("hi, how are you?") is True

    def test_true_for_a_trivial_factual_question(self):
        assert model_router.is_simple_message("what's the capital of France") is True

    def test_false_for_empty_or_whitespace_only(self):
        assert model_router.is_simple_message("") is False
        assert model_router.is_simple_message("   ") is False

    def test_false_when_over_the_length_cap(self):
        assert model_router.is_simple_message("hi " * 100) is False

    def test_false_for_emotionally_or_intellectually_weighted_keywords(self):
        assert (
            model_router.is_simple_message("why do I feel so anxious lately") is False
        )
        assert model_router.is_simple_message("can you explain how this works") is False
        assert (
            model_router.is_simple_message("I'm worried about our relationship")
            is False
        )

    def test_false_for_code_fences(self):
        assert model_router.is_simple_message("```python\nprint(1)\n```") is False

    def test_false_for_multiple_questions_in_one_message(self):
        assert (
            model_router.is_simple_message("is it raining? and are you free?") is False
        )


class TestResolveTurnModel:
    def test_returns_base_model_when_no_local_model_configured(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            model_router, "is_ollama_model_warm", lambda *a, **k: called.append(1)
        )
        model, routed = model_router.resolve_turn_model("gpt-4o", "", "hi")
        assert (model, routed) == ("gpt-4o", False)
        assert called == []

    def test_returns_base_model_when_message_is_not_simple(self, monkeypatch):
        monkeypatch.setattr(model_router, "is_ollama_model_warm", lambda *a, **k: True)
        model, routed = model_router.resolve_turn_model(
            "gpt-4o", "ollama/gemma2:9b", "why do I feel this way about everything"
        )
        assert (model, routed) == ("gpt-4o", False)

    def test_routes_local_when_simple_and_warm(self, monkeypatch):
        monkeypatch.setattr(model_router, "is_ollama_model_warm", lambda *a, **k: True)
        model, routed = model_router.resolve_turn_model(
            "gpt-4o", "ollama/gemma2:9b", "hi there"
        )
        assert (model, routed) == ("ollama/gemma2:9b", True)

    def test_falls_back_and_warms_in_background_when_simple_but_cold(self, monkeypatch):
        monkeypatch.setattr(model_router, "is_ollama_model_warm", lambda *a, **k: False)
        warmed = []
        monkeypatch.setattr(
            "sympose.compactor.run_hygiene_task",
            lambda target, *a, **k: warmed.append((target, a, k)),
        )

        model, routed = model_router.resolve_turn_model(
            "gpt-4o", "ollama/gemma2:9b", "hi there", keep_alive="30m"
        )

        assert (model, routed) == ("gpt-4o", False)
        assert len(warmed) == 1
        target, args, kwargs = warmed[0]
        assert target is model_router.warm_ollama_model
        assert args == ("ollama/gemma2:9b",)
        assert kwargs == {"keep_alive": "30m"}
