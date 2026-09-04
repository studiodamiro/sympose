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

    def test_spawn_worker_tag(self):
        text = "[SPAWN_WORKER: skills=research | task=Find the latest Python version]"
        tags = ActionProcessor.parse_action_tags(text)
        assert len(tags) == 1
        assert tags[0][0] == "SPAWN_WORKER"

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
