"""
Unit tests for sympose.models — provider-key resolution (resolve_api_key)
and the local-Ollama discovery helper. Neither had a dedicated test file
before this: resolve_api_key is a newly-consolidated single source of
truth for logic that used to be copy-pasted across five call sites
(engine.py, workers.py, compactor.py, memory.py x2, sessions.py).
"""

import json

from sympose import models


class TestResolveApiKey:
    def test_gemini_prefix(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "g-secret")
        assert models.resolve_api_key("gemini/gemini-3.6-flash") == "g-secret"

    def test_anthropic_prefix(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a-secret")
        assert models.resolve_api_key("anthropic/claude-sonnet-5") == "a-secret"

    def test_openai_prefix(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o-secret")
        assert models.resolve_api_key("openai/gpt-5") == "o-secret"

    def test_openrouter_prefix(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
        assert models.resolve_api_key("openrouter/x/y") == "or-secret"

    def test_openrouter_routed_anthropic_model_uses_openrouter_key(self, monkeypatch):
        # "openrouter/anthropic/..." must match "openrouter/" only, never
        # the "anthropic/" prefix nested inside it.
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a-secret")
        assert (
            models.resolve_api_key("openrouter/anthropic/claude-sonnet-5")
            == "or-secret"
        )

    def test_none_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert models.resolve_api_key("gemini/gemini-3.6-flash") is None

    def test_none_for_local_ollama_model(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "g-secret")  # must not leak in
        assert models.resolve_api_key("ollama/gemma2:9b") is None

    def test_none_for_unrecognized_prefix(self):
        assert models.resolve_api_key("some-unknown-provider/model") is None


class TestGetLocalOllamaModels:
    def test_returns_pulled_model_names(self, monkeypatch):
        def fake_urlopen(req, timeout=None):
            class _Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return json.dumps(
                        {"models": [{"name": "gemma2:9b"}, {"name": "qwen2.5:14b"}]}
                    ).encode()

            return _Resp()

        monkeypatch.setattr(models.urllib.request, "urlopen", fake_urlopen)
        assert models.get_local_ollama_models() == ["gemma2:9b", "qwen2.5:14b"]

    def test_empty_list_when_ollama_unreachable(self, monkeypatch):
        def _raise(*a, **k):
            raise OSError("connection refused")

        monkeypatch.setattr(models.urllib.request, "urlopen", _raise)
        assert models.get_local_ollama_models() == []

    def test_empty_list_on_malformed_response(self, monkeypatch):
        class _BadResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"not json"

        monkeypatch.setattr(
            models.urllib.request, "urlopen", lambda *a, **k: _BadResp()
        )
        assert models.get_local_ollama_models() == []
