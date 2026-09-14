"""
Unit tests for sympose.model_router's Ollama warm-check/warm-up helpers.
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
