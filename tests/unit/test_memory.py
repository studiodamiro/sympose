"""
Unit tests for sympose.memory — HeuristicGatedExtractor and SessionArchivist.

Regression, found live: "Damiro likes his coffee black" and "Damiro likes
his coffee black." (two independently-phrased identity/preference facts,
same story) both ended up in the same persona's working memory, alongside
lines like "Assistant invoked the vault_read sub-agent skill to query the
Obsidian workspace" — process narration, not a fact about the user at all.
Root cause: neither extraction path (the per-turn HeuristicGatedExtractor,
or SessionArchivist's end-of-session summary) was ever shown the memory
file's existing content before deciding what counted as a new, durable
fact, and the session-summary prompt never restricted extraction to facts
about the user. Both prompts now receive the existing memory file content
and are told to skip anything already covered and never extract the
assistant's own process.
"""

import os
import types

import pytest

from sympose.memory import HeuristicGatedExtractor, SessionArchivist
from sympose.profiles import ProfileManager


def _resp(content: str):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
    )


def _cfg():
    from sympose.config import config_manager

    return config_manager


@pytest.fixture
def pm_with_persona(tmp_path):
    (tmp_path / "sam.yaml").write_text(
        "name: Sam\nhandle: sam\nmemory_file: sam_memory.md\n"
    )
    (tmp_path / "sam_memory.md").write_text(
        "# Sam Working Memory\n- Damiro likes his coffee black.\n"
    )
    return ProfileManager(profiles_dir=str(tmp_path))


class TestHeuristicExtractorSeesExistingMemory:
    def test_existing_memory_is_included_in_the_prompt(
        self, pm_with_persona, monkeypatch
    ):
        seen_prompts = []

        def fake_completion(**kwargs):
            seen_prompts.append(kwargs["messages"][0]["content"])
            return _resp("NONE")

        monkeypatch.setattr("sympose.memory.litellm.completion", fake_completion)
        monkeypatch.setattr(
            "sympose.memory.run_hygiene_task", lambda target, *a, **k: target()
        )

        HeuristicGatedExtractor.extract_async(
            "sam",
            "i prefer my coffee black, always have",
            "Got it, noted.",
            pm_with_persona,
            _cfg(),
        )

        assert len(seen_prompts) == 1
        assert "coffee black" in seen_prompts[0]

    def test_llm_declining_as_duplicate_appends_nothing(
        self, pm_with_persona, monkeypatch
    ):
        """The LLM, shown the existing memory, recognizes the new message as
        a restatement of something already recorded and says NONE - nothing
        new should land in the file."""

        def fake_completion(**kwargs):
            return _resp("NONE")

        monkeypatch.setattr("sympose.memory.litellm.completion", fake_completion)
        monkeypatch.setattr(
            "sympose.memory.run_hygiene_task", lambda target, *a, **k: target()
        )

        mem_path = os.path.join(pm_with_persona.profiles_dir, "sam_memory.md")
        before_text = open(mem_path).read()

        HeuristicGatedExtractor.extract_async(
            "sam",
            "my favorite drink is black coffee, as always",
            "Got it.",
            pm_with_persona,
            _cfg(),
        )

        after_text = open(mem_path).read()
        assert after_text == before_text


class TestSessionSummarySeesExistingMemory:
    def test_existing_memory_included_and_none_appends_nothing(
        self, pm_with_persona, monkeypatch
    ):
        seen_prompts = []

        def fake_completion(**kwargs):
            seen_prompts.append(kwargs["messages"][0]["content"])
            return _resp(
                "### SECTION 1: PERSISTENT MEMORY BULLETS\nNONE\n\n"
                "### SECTION 2: OBSIDIAN SESSION LOG\n## Overview\nQuiet session.\n"
            )

        monkeypatch.setattr("sympose.memory.litellm.completion", fake_completion)

        archivist = SessionArchivist(pm_with_persona)
        result = archivist.summarize_session(
            "sam",
            [
                {"role": "user", "content": "hey, my coffee is black as usual"},
                {"role": "assistant", "content": "noted!"},
            ],
            target="memory",
        )

        assert len(seen_prompts) == 1
        assert "coffee black" in seen_prompts[0]
        assert result.get("targets_saved") in (None, [])

    def test_genuinely_new_fact_still_gets_saved(self, pm_with_persona, monkeypatch):
        def fake_completion(**kwargs):
            return _resp(
                "### SECTION 1: PERSISTENT MEMORY BULLETS\n"
                "- Damiro's dog is named Biscuit.\n\n"
                "### SECTION 2: OBSIDIAN SESSION LOG\n## Overview\nTalked about pets.\n"
            )

        monkeypatch.setattr("sympose.memory.litellm.completion", fake_completion)

        archivist = SessionArchivist(pm_with_persona)
        result = archivist.summarize_session(
            "sam",
            [{"role": "user", "content": "my dog is named Biscuit"}],
            target="memory",
        )

        assert result["status"] == "success"
        assert any("Memory" in t for t in result["targets_saved"])
