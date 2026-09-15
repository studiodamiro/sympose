"""
Unit tests for sympose.actions.ActionProcessor
Covers: parse_action_tags (all tag names, nested brackets, placeholder filtering,
        ACTION: prefix variant, malformed tags) and CONFIG_SET logic.
"""

import pytest
from sympose.actions import ActionProcessor


# ---------------------------------------------------------------------------
# parse_action_tags — basic tag extraction
# ---------------------------------------------------------------------------

class TestParseActionTags:
    def test_single_remember_tag(self):
        text = "[REMEMBER: User likes dark mode]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        tag, inner, raw = tags[0]
        assert tag == "REMEMBER"
        assert inner == "User likes dark mode"

    def test_write_note_tag(self):
        text = "[WRITE_NOTE: path=Ideas/todo.md | content=Buy milk]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "WRITE_NOTE"
        assert "Ideas/todo.md" in tags[0][1]

    def test_daily_note_tag(self):
        text = "[DAILY_NOTE: ## Summary\n- Point A]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "DAILY_NOTE"

    def test_config_set_tag(self):
        text = "[CONFIG_SET: performance.stream=false]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "CONFIG_SET"
        assert "performance.stream=false" in tags[0][1]

    def test_multiple_tags_in_one_text(self):
        text = "[REMEMBER: loves coffee] Some text [DAILY_NOTE: morning notes]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 2
        tag_names = [t[0] for t in tags]
        assert "REMEMBER" in tag_names
        assert "DAILY_NOTE" in tag_names

    def test_action_prefix_variant(self):
        text = "[ACTION:REMEMBER: User prefers short replies]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "REMEMBER"
        assert "User prefers short replies" in tags[0][1]

    def test_case_insensitive_tag_name(self):
        text = "[remember: user dislikes emojis]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "REMEMBER"

    def test_no_tags_returns_empty(self):
        tags = ActionProcessor.parse_action_tags("Just a normal reply, no tags here.")
        assert tags == []

    def test_incomplete_tag_not_parsed(self):
        text = "[REMEMBER: missing closing bracket"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags == []

    def test_nested_brackets_in_content(self):
        """Tags with nested brackets in content (e.g. markdown links) should parse correctly."""
        text = "[WRITE_NOTE: path=Notes/ref.md | content=See [[other note]] for details]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert "[[other note]]" in tags[0][1]

    def test_documentation_placeholder_filtered(self):
        """Tags that look like doc template placeholders should be ignored."""
        text = "[REMEMBER: <content>]"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags == []

    def test_handle_placeholder_filtered(self):
        text = "[CREATE_PERSONA: <handle> | <manifest>]"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags == []

    def test_path_placeholder_filtered(self):
        text = "[WRITE_NOTE: path=<path> | content=hello]"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags == []

    def test_unknown_tag_not_parsed(self):
        text = "[UNKNOWN_TAG: something]"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags == []

    def test_spawn_sub_agent_tag(self):
        text = "[SPAWN_SUB_AGENT: skills=research | task=Find the latest Python version]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "SPAWN_SUB_AGENT"

    def test_react_tag(self):
        text = "[REACT: 👍]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "REACT"

    def test_write_canvas_tag(self):
        text = "[WRITE_CANVAS: target=slack:#general | content=Hello canvas]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "WRITE_CANVAS"

    def test_raw_tag_preserved(self):
        """raw_tag (third element of tuple) should contain the full original text."""
        text = "[REMEMBER: User's birthday is in July]"
        tags = ActionProcessor.parse_action_tags(text)
        assert tags[0][2] == "[REMEMBER: User's birthday is in July]"

    def test_tag_surrounded_by_text(self):
        text = "Sure! [REMEMBER: prefers dark mode] Done."
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][1] == "prefers dark mode"

    def test_all_registered_tag_names_parseable(self):
        """Every TAG_NAMES entry should be parseable with simple content."""
        for tag_name in ActionProcessor.TAG_NAMES:
            text = f"[{tag_name}: simple content here]"
            tags = ActionProcessor.parse_action_tags(text)
            assert len(tags) == 1, f"Failed to parse [{tag_name}: ...]"
            assert tags[0][0] == tag_name


# ---------------------------------------------------------------------------
# parse_action_tags — edge cases
# ---------------------------------------------------------------------------

class TestParseActionTagsEdgeCases:
    def test_empty_string(self):
        assert ActionProcessor.parse_action_tags("") == []

    def test_only_whitespace(self):
        assert ActionProcessor.parse_action_tags("   \n\t  ") == []

    def test_consecutive_tags(self):
        text = "[REMEMBER: fact one][REMEMBER: fact two]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 2

    def test_tag_with_unicode_content(self):
        text = "[REMEMBER: 日本語テスト — Unicode content ✨]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert "日本語" in tags[0][1]

    def test_multiline_tag_content(self):
        text = "[DAILY_NOTE: ## Header\n- Bullet 1\n- Bullet 2]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert "Bullet 2" in tags[0][1]


# ---------------------------------------------------------------------------
# execute_actions — malformed-tag badges (ADR-071)
#
# A recognized tag whose shape doesn't match any handler (e.g. WRITE_NOTE
# missing its `|content` half) must surface a warning badge rather than
# silently doing nothing — the model otherwise has no signal its action
# didn't run (ground-truth sovereignty, ADR-024).
# ---------------------------------------------------------------------------

class _FakeProfileManager:
    """Minimal stand-in for ProfileManager, just enough for execute_actions."""

    def get_profile(self, handle):
        return {"name": "Test Persona", "vault_folder": "Test", "share_memory": False}


class TestExecuteActionsMalformedTags:
    def test_write_note_missing_pipe_produces_warning_badge(self):
        pm = _FakeProfileManager()
        _, badges = ActionProcessor.execute_actions(pm, "test", "[WRITE_NOTE: just-a-filename-no-content]")
        assert any("Malformed" in b and "WRITE_NOTE" in b for b in badges)

    def test_read_note_missing_target_produces_warning_badge(self):
        pm = _FakeProfileManager()
        _, badges = ActionProcessor.execute_actions(pm, "test", "[READ_NOTE:]")
        assert any("Malformed" in b and "READ_NOTE" in b for b in badges)

    def test_well_formed_write_note_produces_no_malformed_badge(self, monkeypatch):
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.write_note",
            lambda profile, filename, content: None,
        )
        _, badges = ActionProcessor.execute_actions(pm, "test", "[WRITE_NOTE: todo.md | Buy milk]")
        assert not any("Malformed" in b for b in badges)
        assert any("saved note" in b for b in badges)

    def test_spawn_sub_agent_missing_pipe_produces_warning_badge(self):
        """The audit's named example (a model omitting the `<skills> |` half
        entirely) — already fixed 2026-09-04 by this same catch-all, before
        the audit ran; this pins the specific tag down with its own test
        rather than only the generic WRITE_NOTE/READ_NOTE cases above."""
        pm = _FakeProfileManager()
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[SPAWN_SUB_AGENT: find my notes about Dylan]"
        )
        assert any("Malformed" in b and "SPAWN_SUB_AGENT" in b for b in badges)


class TestInventedPseudoTagsAreStripped:
    """Live bug: a local model, narrating a roleplay "game", ended its reply
    with `[GAME_STATE_UPDATE]` — its own invented bracket notation, mimicking
    the shape of a real action tag but matching no real tag name. Nothing
    recognized it, so it printed as raw literal text. Caught by shape (an
    all-caps, underscored identifier alone in brackets) rather than by
    naming this one specific invented tag, so any other one a model dreams
    up next is caught the same way."""

    def test_bare_invented_tag_is_removed(self):
        pm = _FakeProfileManager()
        clean, _ = ActionProcessor.execute_actions(
            pm, "test", "Here is your note.\n\n[GAME_STATE_UPDATE]"
        )
        assert "GAME_STATE_UPDATE" not in clean
        assert "Here is your note." in clean

    def test_invented_tag_with_a_colon_is_also_removed(self):
        pm = _FakeProfileManager()
        clean, _ = ActionProcessor.execute_actions(
            pm, "test", "Rolling now. [ROLL_DICE: 6] You got a six!"
        )
        assert "ROLL_DICE" not in clean
        assert "You got a six!" in clean

    def test_a_real_recognized_tag_is_not_double_mangled(self, monkeypatch):
        # A real tag name is excluded from the pseudo-tag pattern so this
        # stays governed entirely by the real WRITE_NOTE handling above -
        # not something this catch-all also tries to match.
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.write_note",
            lambda profile, filename, content: None,
        )
        clean, badges = ActionProcessor.execute_actions(
            pm, "test", "[WRITE_NOTE: todo.md | Buy milk]"
        )
        assert any("saved note" in b for b in badges)
        assert not any("Malformed" in b for b in badges)

    def test_footnotes_and_markdown_links_survive(self):
        pm = _FakeProfileManager()
        clean, _ = ActionProcessor.execute_actions(
            pm,
            "test",
            "See [1] and [a check](https://example.com) and [[a Wikilink]].",
        )
        assert "[1]" in clean
        assert "[a check](https://example.com)" in clean
        assert "[[a Wikilink]]" in clean


class TestSubAgentReadNoteFoldsVerbatimContent:
    """Regression: a `vault_read` sub-agent that surfaced a note via
    `[READ_NOTE]` rendered it to the terminal panel only — the report handed
    back to the primary persona (and Slack) had no note text, so a weak
    model quoted a plausible fabrication. The sub-agent path must fold the
    verbatim content into its returned synthesis."""

    def test_sub_agent_read_note_appends_ground_truth_block(self, monkeypatch):
        pm = _FakeProfileManager()
        body = "---\nentry: 2024-04-20\n---\nIm fixing the layout of Benns resume. I feel devastated."
        monkeypatch.setattr("sympose.actions.VaultManager.resolve_note_target",
                            lambda profile, t: ("Daily/2024/04-April/2024-04-20.md", "/abs/x.md"))
        monkeypatch.setattr("sympose.actions.VaultManager.read_note", lambda profile, p: body)
        monkeypatch.setattr("sympose.ui.TerminalUI.render_vault_note_panel", lambda *a, **k: None)

        clean, badges = ActionProcessor.execute_actions(
            pm, "sub_agent", "Here's the entry: [READ_NOTE: Daily/2024/04-April/2024-04-20.md]"
        )
        assert "### Ground-Truth Sandboxed Vault Note" in clean
        assert "fixing the layout of Benns resume" in clean
        assert "I feel devastated" in clean

    def test_primary_persona_read_note_does_not_fold_content(self, monkeypatch):
        """Only the sub-agent path folds text; a primary persona's [READ_NOTE]
        still just renders the panel (that transcript is user-facing already)."""
        pm = _FakeProfileManager()
        monkeypatch.setattr("sympose.actions.VaultManager.resolve_note_target",
                            lambda profile, t: ("N.md", "/abs/N.md"))
        monkeypatch.setattr("sympose.actions.VaultManager.read_note", lambda profile, p: "secret body")
        monkeypatch.setattr("sympose.ui.TerminalUI.render_vault_note_panel", lambda *a, **k: None)

        clean, badges = ActionProcessor.execute_actions(pm, "test", "[READ_NOTE: N.md]")
        assert "secret body" not in clean
        assert any("rendered note to Terminal" in b for b in badges)


class TestExecuteActionsThreadsOnProgressToSubAgent:
    """`on_progress` lets a caller show live tool-call status instead of a
    silent wait for the whole sub-agent loop — must reach
    SubAgentEngine.execute_sub_agent_task unchanged."""

    def test_on_progress_is_passed_through_to_the_sub_agent_call(self, monkeypatch):
        pm = _FakeProfileManager()
        received = {}

        def fake_execute_sub_agent_task(task, on_progress=None):
            received["on_progress"] = on_progress
            return "the answer", ["read_file(path=x)"]

        monkeypatch.setattr(
            "sympose.actions.SubAgentEngine.execute_sub_agent_task",
            fake_execute_sub_agent_task,
        )

        sentinel = lambda s: None  # noqa: E731
        ActionProcessor.execute_actions(
            pm,
            "test",
            "[SPAWN_SUB_AGENT: vault_read | find my notes]",
            on_progress=sentinel,
        )
        assert received["on_progress"] is sentinel

    def test_on_progress_defaults_to_none_when_omitted(self, monkeypatch):
        pm = _FakeProfileManager()
        received = {}

        def fake_execute_sub_agent_task(task, on_progress=None):
            received["on_progress"] = on_progress
            return "the answer", []

        monkeypatch.setattr(
            "sympose.actions.SubAgentEngine.execute_sub_agent_task",
            fake_execute_sub_agent_task,
        )

        ActionProcessor.execute_actions(
            pm, "test", "[SPAWN_SUB_AGENT: vault_read | find my notes]"
        )
        assert received["on_progress"] is None


class TestSubAgentTaskCarriesTheUsersOwnWords:
    """Live bug: asked to play an established ritual ("our favorite game")
    scoped to a specific folder, the model's own [SPAWN_SUB_AGENT] tag
    condensed the task down to a bare "Roulette", dropping the folder
    constraint entirely - the sub-agent then searched the whole vault. The
    tag's task string is a paraphrase from whichever model is driving the
    turn; appending the user's own literal words mechanically means a
    dropped constraint still reaches the sub-agent regardless of which
    model authored the paraphrase."""

    def test_users_literal_message_is_appended_to_a_terse_task(self, monkeypatch):
        pm = _FakeProfileManager()
        received = {}

        def fake_execute_sub_agent_task(task, on_progress=None):
            received["task_prompt"] = task.task_prompt
            return "the answer", []

        monkeypatch.setattr(
            "sympose.actions.SubAgentEngine.execute_sub_agent_task",
            fake_execute_sub_agent_task,
        )

        ActionProcessor.execute_actions(
            pm,
            "test",
            "[SPAWN_SUB_AGENT: vault_read | Roulette]",
            user_prompt="lets play our favorite game. lets do from Daily folder. g?",
        )
        assert "Roulette" in received["task_prompt"]
        assert "Daily folder" in received["task_prompt"]

    def test_not_duplicated_when_the_task_already_contains_it(self, monkeypatch):
        pm = _FakeProfileManager()
        received = {}

        def fake_execute_sub_agent_task(task, on_progress=None):
            received["task_prompt"] = task.task_prompt
            return "the answer", []

        monkeypatch.setattr(
            "sympose.actions.SubAgentEngine.execute_sub_agent_task",
            fake_execute_sub_agent_task,
        )

        ActionProcessor.execute_actions(
            pm,
            "test",
            "[SPAWN_SUB_AGENT: vault_read | pull a random note from Daily]",
            user_prompt="pull a random note from Daily",
        )
        assert received["task_prompt"].count("pull a random note from Daily") == 1

    def test_no_user_prompt_leaves_the_task_untouched(self, monkeypatch):
        pm = _FakeProfileManager()
        received = {}

        def fake_execute_sub_agent_task(task, on_progress=None):
            received["task_prompt"] = task.task_prompt
            return "the answer", []

        monkeypatch.setattr(
            "sympose.actions.SubAgentEngine.execute_sub_agent_task",
            fake_execute_sub_agent_task,
        )

        ActionProcessor.execute_actions(
            pm, "test", "[SPAWN_SUB_AGENT: vault_read | Roulette]"
        )
        assert received["task_prompt"] == "Roulette"


# ---------------------------------------------------------------------------
# execute_actions — CREATE_PERSONA soul_content extraction (ADR-075)
#
# A manifest's `soul_content` field must be written directly to
# <handle>_soul.md and stripped out of the saved .yaml, so a persona created
# from a described reference figure actually gets a grounded soul instead of
# ProfileManager's generic one-sentence auto-bootstrap fallback.
# ---------------------------------------------------------------------------

class _FakeProfileManagerWithDisk:
    """Stand-in for ProfileManager backed by a real tmp_path profiles_dir, so
    CREATE_PERSONA's direct file writes can be inspected afterward."""

    def __init__(self, profiles_dir):
        self.profiles_dir = str(profiles_dir)

    def reload_profiles(self):
        pass

    def get_profile(self, handle):
        return {"name": handle.title(), "handle": handle}


class TestExecuteActionsCreatePersonaSoulContent:
    def test_soul_content_written_to_soul_file_not_yaml(self, tmp_path):
        pm = _FakeProfileManagerWithDisk(tmp_path)
        manifest = (
            "name: \"Marie Curie\"\n"
            "handle: \"curie\"\n"
            "title: \"Research Specialist\"\n"
            "soul_content: |\n"
            "  # Marie Curie: Core Directives\n"
            "  Insist on evidence before accepting a claim.\n"
        )
        text = f"[CREATE_PERSONA: curie | {manifest}]"
        _, badges = ActionProcessor.execute_actions(pm, "test", text)

        soul_path = tmp_path / "curie_soul.md"
        yaml_path = tmp_path / "curie.yaml"
        assert soul_path.exists()
        assert "Insist on evidence" in soul_path.read_text()
        assert "soul_content" not in yaml_path.read_text()
        assert any("custom soul" in b for b in badges)

    def test_no_soul_content_leaves_yaml_intact_and_writes_no_soul_file(self, tmp_path):
        pm = _FakeProfileManagerWithDisk(tmp_path)
        manifest = 'name: "Archimedes"\nhandle: "archimedes"\ntitle: "Engineer"\n'
        text = f"[CREATE_PERSONA: archimedes | {manifest}]"
        _, badges = ActionProcessor.execute_actions(pm, "test", text)

        assert (tmp_path / "archimedes.yaml").exists()
        assert not (tmp_path / "archimedes_soul.md").exists()
        assert not any("custom soul" in b for b in badges)

    def test_malformed_yaml_falls_back_to_raw_write(self, tmp_path):
        """soul_content extraction is best-effort — unparseable YAML must
        still write the manifest as-is rather than losing the persona."""
        pm = _FakeProfileManagerWithDisk(tmp_path)
        text = "[CREATE_PERSONA: broken | name: \"Broken\": : not valid yaml :::]"
        _, badges = ActionProcessor.execute_actions(pm, "test", text)
        assert (tmp_path / "broken.yaml").exists()


class TestExecuteActionsConfigSetAndDeletePersona:
    """Regression, found live: `config_manager` was only ever imported
    locally inside the VIEW_NOTE branch. Since Python decides a name is
    local to the whole function at compile time, that made `config_manager`
    a local variable throughout execute_actions — so CONFIG_SET and
    DELETE_PERSONA, which both reference it in their own branches with no
    import of their own, crashed with `UnboundLocalError: cannot access
    local variable 'config_manager'` any time they ran without a VIEW_NOTE
    tag having already executed first in the same call. Confirmed live: a
    plain "delete the testbot persona" request crashed outright. Fixed by
    importing `config_manager` once at module scope instead."""

    def test_config_set_alone_does_not_crash(self, monkeypatch):
        import sympose.actions as actions_mod

        calls = {}
        monkeypatch.setattr(
            actions_mod.config_manager, "set", lambda k, v: calls.setdefault("set", (k, v))
        )
        monkeypatch.setattr(actions_mod.config_manager, "save", lambda: calls.setdefault("saved", True))
        pm = _FakeProfileManager()
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[CONFIG_SET: performance.stream | false]"
        )
        assert calls["set"] == ("performance.stream", False)
        assert calls["saved"] is True
        assert any("updated runtime configuration" in b for b in badges)

    def test_delete_persona_alone_does_not_crash(self, tmp_path, monkeypatch):
        import sympose.actions as actions_mod

        monkeypatch.setattr(actions_mod.config_manager, "get", lambda k: "samantha")
        (tmp_path / "testbot.yaml").write_text("name: Test Bot\nhandle: testbot\n")
        (tmp_path / "testbot_soul.md").write_text("A friendly test assistant.")
        pm = _FakeProfileManagerWithDisk(tmp_path)
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[DELETE_PERSONA: testbot]"
        )
        assert not (tmp_path / "testbot.yaml").exists()
        assert (tmp_path / "_archived" / "testbot" / "testbot.yaml").exists()
        assert any("deleted persona" in b for b in badges)

    def test_delete_persona_not_found_gets_honest_badge(self, tmp_path, monkeypatch):
        import sympose.actions as actions_mod

        monkeypatch.setattr(actions_mod.config_manager, "get", lambda k: "samantha")
        pm = _FakeProfileManagerWithDisk(tmp_path)
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[DELETE_PERSONA: ghost]"
        )
        assert any("not found" in b for b in badges)


class _FakeProfileManagerWithMemory(_FakeProfileManager):
    def __init__(self, append_memory_result: bool = True):
        self._append_memory_result = append_memory_result
        self.append_memory_calls: list[tuple[str, str]] = []

    def append_memory(self, handle, fact):
        self.append_memory_calls.append((handle, fact))
        return self._append_memory_result


class TestExecuteActionsHonestFailureBadges:
    """Regression: WRITE_NOTE/APPEND_NOTE/DAILY_NOTE/REMEMBER discarded the
    return value of the underlying vault_write.py / append_memory call and
    unconditionally showed a success badge - so a rejected write (sandbox
    violation, the Daily/ boundary guard, a disk error) was confirmed to the
    user as a success every time. Found live: asking Samantha to write
    directly into Daily/ produced "Samantha saved note to Vault: Daily/..."
    even though vault_write.py correctly refused and no file was created."""

    def test_write_note_failure_produces_warning_not_success_badge(self, monkeypatch):
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.write_note",
            lambda profile, filename, content: "Warning: Daily/ is reserved for daily entries — use [DAILY_NOTE] instead of writing directly into that folder.",
        )
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[WRITE_NOTE: Daily/test.md | hello]"
        )
        assert any("could not save note" in b for b in badges)
        assert not any("saved note to Vault" in b for b in badges)

    def test_write_note_success_still_produces_success_badge(self, monkeypatch):
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.write_note",
            lambda profile, filename, content: "Saved note: `Thoughts/todo.md`",
        )
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[WRITE_NOTE: todo.md | Buy milk]"
        )
        assert any("saved note to Vault" in b for b in badges)
        assert not any("could not save note" in b for b in badges)

    def test_append_note_failure_produces_warning_not_success_badge(self, monkeypatch):
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.append_note",
            lambda profile, filename, content: "Security Error: Target path `../etc/passwd` is outside assigned sandbox.",
        )
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[APPEND_NOTE: ../etc/passwd | pwned]"
        )
        assert any("could not append to note" in b for b in badges)
        assert not any("appended to Vault note" in b for b in badges)

    def test_daily_note_failure_produces_warning_not_success_badge(self, monkeypatch):
        pm = _FakeProfileManager()
        monkeypatch.setattr(
            "sympose.actions.VaultManager.write_daily_note",
            lambda profile, reflection: "Error: Failed to write daily note: disk full",
        )
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[DAILY_NOTE: rough day today]"
        )
        assert any("could not log daily entry" in b for b in badges)
        assert not any("logged entry to Daily Notes" in b for b in badges)

    def test_remember_failure_produces_warning_not_success_badge(self):
        pm = _FakeProfileManagerWithMemory(append_memory_result=False)
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[REMEMBER: favorite color is chartreuse]"
        )
        assert any("could not persist to memory" in b for b in badges)
        assert not any("updated" in b and "memory" in b for b in badges)

    def test_remember_success_still_produces_success_badge(self):
        pm = _FakeProfileManagerWithMemory(append_memory_result=True)
        _, badges = ActionProcessor.execute_actions(
            pm, "test", "[REMEMBER: favorite color is chartreuse]"
        )
        assert any("updated" in b and "memory" in b for b in badges)
