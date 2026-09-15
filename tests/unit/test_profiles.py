"""
Unit tests for sympose.profiles.ProfileManager.bootstrap_missing_artifacts —
the fallback soul-file scaffold used when a persona manifest doesn't provide
`soul_content` (ADR-075.2) — and `set_persona_field`, the `/persona set` write path.
"""

import os
import pytest
import yaml

from sympose.profiles import ProfileManager


class TestBootstrapMissingArtifactsFallbackSoul:
    def test_fallback_soul_is_more_than_one_sentence(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        pm.bootstrap_missing_artifacts({"handle": "archimedes", "name": "Archimedes", "title": "Engineer"})

        soul_path = tmp_path / "archimedes_soul.md"
        assert soul_path.exists()
        content = soul_path.read_text()
        assert "Anti-Hallucination" in content
        assert content.count("\n") > 3, "fallback soul should be a real scaffold, not one line"

    def test_does_not_overwrite_an_existing_soul_file(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        soul_path = tmp_path / "archimedes_soul.md"
        soul_path.write_text("# Archimedes\n\nCustom hand-written soul.\n")

        pm.bootstrap_missing_artifacts({"handle": "archimedes", "name": "Archimedes", "title": "Engineer"})

        assert "Custom hand-written soul" in soul_path.read_text()

    def test_respects_explicit_soul_file_path(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        pm.bootstrap_missing_artifacts({
            "handle": "curie", "name": "Marie Curie", "title": "Researcher",
            "soul_file": "profiles/curie_soul.md",
        })
        assert (tmp_path / "curie_soul.md").exists()


class TestSetPersonaField:
    def _seed(self, tmp_path):
        (tmp_path / "sam.yaml").write_text(
            'name: "Sam"\nhandle: "sam"\nmodel: ""\nskills:\n  - vault_recall\n'
        )
        return ProfileManager(profiles_dir=str(tmp_path))

    def test_writes_and_coerces_a_persona_knob(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("@sam", "temperature", "0.7")
        assert ok
        data = yaml.safe_load((tmp_path / "sam.yaml").read_text())
        assert data["temperature"] == 0.7  # coerced to float, not "0.7"

    def test_rejects_a_global_key_with_a_pointer_to_config(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "performance.stream", "true")
        assert not ok and "/config set" in msg

    def test_rejects_an_out_of_range_value(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "temperature", "9")
        assert not ok and "<=" in msg
        assert "temperature" not in yaml.safe_load((tmp_path / "sam.yaml").read_text())

    def test_rejects_a_bad_enum(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "vault_grounding", "loose")
        assert not ok and "auto" in msg

    def test_unknown_persona_is_reported(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("nobody", "temperature", "0.5")
        assert not ok and "not found" in msg


class TestGetPersonaMemory:
    """Public accessor added so sub_agents.py can hand a delegated sub-agent
    the parent persona's working memory without reaching into the protected
    `_read_file_safe` helper."""

    def test_returns_the_memory_files_content(self, tmp_path):
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nmemory_file: sam_memory.md\n"
        )
        (tmp_path / "sam_memory.md").write_text(
            "- Favorite game is Vault Roulette.\n"
        )

        pm = ProfileManager(profiles_dir=str(tmp_path))
        assert "Vault Roulette" in pm.get_persona_memory(pm.get_profile("sam"))

    def test_returns_empty_string_when_no_memory_file(self, tmp_path):
        (tmp_path / "sam.yaml").write_text("name: Sam\nhandle: sam\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        profile = pm.get_profile("sam")
        profile["memory_file"] = None
        assert pm.get_persona_memory(profile) == ""


class TestFindRelevantMemoryFact:
    """Live bug: a memory bullet can say almost exactly what the user just
    typed ("Damiro's favorite game is 'Vault Roulette'..." vs. "lets play
    our favorite game") and a small local model still doesn't reliably
    notice it mid-file. This is a deterministic, zero-round-trip keyword
    match so the caller can surface the fact explicitly instead of hoping
    the model finds it unassisted - generic across any fact/phrasing, not
    tied to "games" or any one ritual."""

    MEMORY = (
        "# Samantha: Working Memory\n"
        "**Identity & Role**\n"
        "- User's name is Damiro.\n"
        "**Recent Achievements & Personal Interests**\n"
        "- Damiro published his first npm package, stylo.\n"
        "- Damiro's favorite game is \"Vault Roulette,\" where a random "
        "note from his Obsidian vault is pulled and discussed.\n"
        "- Damiro likes his coffee black.\n"
    )

    def test_matches_a_near_verbatim_phrase(self):
        hit = ProfileManager.find_relevant_memory_fact(
            self.MEMORY, "hey sam lets play our favorite game. lets do Movies. g!"
        )
        assert hit is not None
        assert "Vault Roulette" in hit

    def test_matches_a_differently_worded_follow_up(self):
        hit = ProfileManager.find_relevant_memory_fact(
            self.MEMORY, "dont you remember our favorite game?"
        )
        assert hit is not None
        assert "Vault Roulette" in hit

    def test_no_match_for_an_unrelated_message(self):
        hit = ProfileManager.find_relevant_memory_fact(
            self.MEMORY, "what's the weather like for a hike this weekend?"
        )
        assert hit is None

    def test_single_shared_word_is_not_enough(self):
        """A lone incidental overlap (e.g. just "game") shouldn't fire -
        requires at least two shared significant words to avoid noisy
        false positives on short, generic messages."""
        hit = ProfileManager.find_relevant_memory_fact(self.MEMORY, "nice game today")
        assert hit is None

    def test_empty_memory_returns_none(self):
        assert ProfileManager.find_relevant_memory_fact("", "our favorite game") is None

    def test_empty_message_returns_none(self):
        assert ProfileManager.find_relevant_memory_fact(self.MEMORY, "") is None

    def test_picks_the_strongest_of_multiple_candidate_lines(self):
        mem = (
            "- Damiro likes coffee.\n"
            "- Damiro's favorite coffee shop game is trivia night.\n"
            "- Damiro's favorite game is \"Vault Roulette,\" a random vault note pull.\n"
        )
        hit = ProfileManager.find_relevant_memory_fact(mem, "our favorite game, roulette style")
        assert hit is not None
        assert "Vault Roulette" in hit


class TestBuildSystemPromptOrdering:
    """Regression, found live: a small local model's recall of a fact in
    persona working memory was unreliable when that block sat early in the
    system prompt (before workspace rules and skill playbooks, ~6,000 tokens
    of unrelated text away from the user's actual question). Moving the
    block to the very end - right before the active turns - fixed it with
    the memory content completely unchanged; only its position moved. This
    locks that ordering in so it can't silently drift back to the front.

    The "Stay {name}" persona-consistency reinforcement (added later, same
    session) is deliberately the one block placed after memory - a
    behavioral instruction benefits from the same end-of-prompt recency as
    a factual one, and it doesn't compete with recalling memory content
    since it's a different kind of thing entirely."""

    def test_persona_memory_comes_after_the_workspace_rules(self, tmp_path):
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
            "memory_file: sam_memory.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")
        (tmp_path / "sam_memory.md").write_text(
            "# Memory\n- The user's favorite game is Vault Roulette.\n"
        )

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        mem_idx = prompt.index("Vault Roulette")
        rules_idx = prompt.index("Grounding & Anti-Hallucination")
        assert mem_idx > rules_idx, (
            "persona memory must come after the workspace rules, not before"
        )

    def test_workspace_rules_cover_theatrical_self_narration(self, tmp_path):
        """The shared, packaged ruleset (every persona, no per-persona edit)
        already forbade process stage directions; broadened live to also
        name third-person scene-setting narration of the persona's own
        reactions, which is what actually slipped through."""
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        assert "third-person narration of your own reactions" in prompt

    def test_workspace_rules_forbid_promising_an_ongoing_auto_save_protocol(
        self, tmp_path
    ):
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        assert "Never promise an ongoing protocol that will keep saving" in prompt

    def test_memory_block_instructs_facts_to_outrank_easier_inventions(
        self, tmp_path
    ):
        """Live bug: "let's play our favorite game, let's do movies" - she
        had the real fact ("favorite game is Vault Roulette") right there
        in memory, but "movies" gave her an easier, unrelated path (a
        movie-trivia game invented from scratch) and she took it instead
        of checking what she actually had. Verified live: with this
        instruction added, the same message correctly recalled "Vault
        Roulette" across three separate runs against the real model."""
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
            "memory_file: sam_memory.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")
        (tmp_path / "sam_memory.md").write_text(
            "# Memory\n- The user's favorite game is Vault Roulette.\n"
        )

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        assert "always outranks a plausible invention" in prompt
        assert prompt.index("always outranks a plausible invention") < prompt.index(
            "Vault Roulette"
        )

    def test_stay_in_character_and_no_phantom_actions_come_after_memory(
        self, tmp_path
    ):
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
            "memory_file: sam_memory.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")
        (tmp_path / "sam_memory.md").write_text(
            "# Memory\n- The user's favorite game is Vault Roulette.\n"
        )

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        mem_idx = prompt.index("Vault Roulette")
        stay_idx = prompt.index("### Stay Sam")
        phantom_idx = prompt.index("### No Phantom Actions")
        moment_idx = prompt.index("### Match The Moment")
        assert stay_idx > mem_idx, (
            "the persona-consistency reinforcement must come after memory"
        )
        assert phantom_idx > stay_idx, (
            "the no-phantom-actions reinforcement must come after Stay {name}"
        )
        assert moment_idx > phantom_idx, (
            "the match-the-moment reinforcement must be the final block"
        )
        assert prompt.rstrip().endswith("not by default.")

    def test_no_phantom_actions_block_names_the_live_failure_pattern(
        self, tmp_path
    ):
        """Live bug: a local model announced "from this point forward,
        every session will be logged" and later "consider it logged" -
        having emitted no real tag and written nothing to disk."""
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        assert "describing an action is not doing it" in prompt
        assert "no such mechanism" in prompt

    def test_match_the_moment_block_forbids_over_formatting_casual_replies(
        self, tmp_path
    ):
        """Live bug: a casual back-and-forth got answered with markdown
        headers, bold section titles, numbered lists, and an emoji-labelled
        "Summary & Commitment" - documentation formatting for an ordinary
        conversational reply. Not a universal brevity rule - a persona
        whose own soul file calls for elaborate prose should stay that way;
        this is about matching structure to what the message needs."""
        (tmp_path / "sam.yaml").write_text(
            "name: Sam\nhandle: sam\nsoul_file: sam_soul.md\n"
        )
        (tmp_path / "sam_soul.md").write_text("# Sam\nYou are Sam.\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("sam"))

        assert "no markdown headers, bold section titles" in prompt
        assert "fewest sentences that fully address" in prompt

    def test_stay_in_character_block_adapts_to_any_persona_name(self, tmp_path):
        """A runtime-level fix, not a per-persona prompt edit: every persona
        gets this the same way, with no YAML/soul-file change required -
        the shipped default Samantha included, and any user-created
        persona with a different name and voice."""
        (tmp_path / "grace.yaml").write_text(
            "name: Grace\nhandle: grace\nsoul_file: grace_soul.md\n"
        )
        (tmp_path / "grace_soul.md").write_text("# Grace\nYou are Grace.\n")

        pm = ProfileManager(profiles_dir=str(tmp_path))
        prompt = pm.build_system_prompt(pm.get_profile("grace"))

        assert "### Stay Grace" in prompt
        assert "You are Grace speaking directly, not an author describing Grace" in prompt
