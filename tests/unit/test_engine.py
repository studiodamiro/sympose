"""
Unit tests for sympose.engine.PersonaEngine._build_kwargs — the litellm call
kwargs assembler. Covers the local-backend `keep_alive` residency passthrough
(persona YAML `keep_alive` → `performance.local_keep_alive` → server env).
"""

import pytest

from sympose.engine import PersonaEngine
from sympose.profiles import ProfileManager


@pytest.fixture
def engine(tmp_path):
    return PersonaEngine(ProfileManager(profiles_dir=str(tmp_path)))


class TestBuildKwargsKeepAlive:
    def test_persona_keep_alive_passed_for_local_model(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {"keep_alive": -1}, [])
        assert kw["keep_alive"] == -1

    def test_persona_keep_alive_string_duration(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {"keep_alive": "30m"}, [])
        assert kw["keep_alive"] == "30m"

    def test_keep_alive_never_sent_for_remote_model(self, engine):
        kw = engine._build_kwargs("gemini/gemini-3.6-flash", {"keep_alive": -1}, [])
        assert "keep_alive" not in kw

    def test_absent_when_unset(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {}, [])
        assert "keep_alive" not in kw

    def test_config_default_applies_when_persona_silent(self, engine):
        engine.config.set("performance.local_keep_alive", -1)
        try:
            kw = engine._build_kwargs("ollama/llama3", {}, [])
            assert kw["keep_alive"] == -1
        finally:
            engine.config.set("performance.local_keep_alive", None)

    def test_persona_overrides_config_default(self, engine):
        engine.config.set("performance.local_keep_alive", "10m")
        try:
            kw = engine._build_kwargs("ollama/llama3", {"keep_alive": 0}, [])
            assert kw["keep_alive"] == 0
        finally:
            engine.config.set("performance.local_keep_alive", None)
