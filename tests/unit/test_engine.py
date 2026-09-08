"""
Unit tests for sympose.engine.PersonaEngine — the litellm call kwargs assembler
(local-backend `keep_alive` residency passthrough) and `_visible_stream`, the
gate that stops user-visible output at the first autonomic retrieval tag.
"""

import types

import pytest

from sympose.engine import PersonaEngine
from sympose.profiles import ProfileManager


@pytest.fixture
def engine(tmp_path):
    return PersonaEngine(ProfileManager(profiles_dir=str(tmp_path)))


def _chunks(*parts):
    """Fake a litellm streaming response from text pieces."""
    for p in parts:
        yield types.SimpleNamespace(
            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=p))]
        )


class TestVisibleStreamGate:
    def _run(self, engine, *parts):
        sink = []
        out = "".join(engine._visible_stream(_chunks(*parts), sink))
        return out, sink[0]

    def test_plain_text_passes_through(self, engine):
        out, raw = self._run(engine, "Here is ", "the whole ", "answer.")
        assert out == "Here is the whole answer."
        assert raw == "Here is the whole answer."

    def test_cuts_at_spawn_worker_tag(self, engine):
        out, raw = self._run(
            engine,
            "Let me check the vault. ",
            "[SPAWN_WORKER: vault_recall | Dylan] ",
            "Here is Dylan's note: Created 2021-06-15, a close friend...",
        )
        assert out == "Let me check the vault. "
        assert "close friend" not in out
        # the raw text still carries the tag for ActionProcessor
        assert "[SPAWN_WORKER: vault_recall | Dylan]" in raw

    def test_cuts_at_search_tag_split_across_chunks(self, engine):
        out, raw = self._run(engine, "One sec ", "[SEA", "RCH: btc price] ", "It is $70k")
        assert out == "One sec "
        assert "70k" not in out

    def test_tag_only_reply_yields_nothing_visible(self, engine):
        out, raw = self._run(engine, "[SPAWN_WORKER: vault_recall | grief]")
        assert out == ""
        assert raw == "[SPAWN_WORKER: vault_recall | grief]"


class TestGroundingModeKnob:
    """`vault_grounding: auto` derives strict/trust from the model: a local
    backend (or localhost api_base) → strict, cloud → trust. An explicit
    `strict`/`trust` on the persona wins."""

    def test_local_ollama_model_is_strict_under_auto(self, engine):
        assert engine._grounding_mode({}, "ollama_chat/qwen2.5:14b") == "strict"
        assert engine._grounding_mode({}, "ollama/llama3.1:8b") == "strict"

    def test_cloud_model_is_trust_under_auto(self, engine):
        assert engine._grounding_mode({}, "gemini/gemini-3.6-flash") == "trust"
        assert engine._grounding_mode({}, "openrouter/x/y") == "trust"

    def test_localhost_api_base_forces_strict(self, engine):
        assert engine._grounding_mode({"api_base": "http://localhost:11434"}, "openai/gpt-x") == "strict"

    def test_explicit_persona_setting_wins(self, engine):
        assert engine._grounding_mode({"vault_grounding": "trust"}, "ollama/llama3") == "trust"
        assert engine._grounding_mode({"vault_grounding": "strict"}, "gemini/flash") == "strict"

    def test_global_default_overrides_auto(self, engine):
        engine.config.set("vault.grounding_default", "strict")
        try:
            assert engine._grounding_mode({}, "gemini/gemini-3.6-flash") == "strict"
        finally:
            engine.config.set("vault.grounding_default", None)


class TestEntityGuess:
    def test_pull_x_entry(self, engine):
        assert engine._entity_guess("Certainly, I can pull Dylan's entry from your vault.") == "Dylan"

    def test_do_you_know_x(self, engine):
        assert engine._entity_guess("do you know dylan?").lower() == "dylan"

    def test_falls_through_to_capitalised_name(self, engine):
        assert engine._entity_guess("what did I say about Marguerite last year") == "Marguerite"

    def test_nothing_when_no_subject(self, engine):
        assert engine._entity_guess("yes, just summarize", "sure go ahead") == ""


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
