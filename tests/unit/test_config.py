"""
Unit tests for sympose.config
Covers: ConfigManager deep-merge, dotpath get/set, is_safe_path, convert_md_to_slack_mrkdwn.
"""

import os
import textwrap
import pytest

from sympose.config import (
    ConfigManager,
    convert_md_to_slack_mrkdwn,
    get_version,
    is_local_backend,
    is_safe_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(tmp_path, yaml_text: str) -> ConfigManager:
    """Write yaml_text to a tmp file and return a ConfigManager loaded from it."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent(yaml_text))
    return ConfigManager(config_path=str(cfg_file))


# ---------------------------------------------------------------------------
# ConfigManager — defaults
# ---------------------------------------------------------------------------

class TestConfigManagerDefaults:
    def test_default_request_timeout(self, tmp_path):
        cm = make_config(tmp_path, "")  # empty yaml → pure defaults
        assert cm.get("performance.request_timeout") == 30.0

    def test_default_max_context_turns(self, tmp_path):
        cm = make_config(tmp_path, "")
        assert cm.get("performance.max_context_turns") == 15

    def test_default_extraction_timeout(self, tmp_path):
        cm = make_config(tmp_path, "")
        assert cm.get("memory.extraction_timeout") == 8.0

    def test_missing_key_returns_default(self, tmp_path):
        cm = make_config(tmp_path, "")
        assert cm.get("nonexistent.key", "fallback") == "fallback"

    def test_missing_key_returns_none_by_default(self, tmp_path):
        cm = make_config(tmp_path, "")
        assert cm.get("nonexistent.key") is None


# ---------------------------------------------------------------------------
# ConfigManager — deep merge
# ---------------------------------------------------------------------------

class TestConfigManagerDeepMerge:
    def test_override_scalar_in_nested_section(self, tmp_path):
        cm = make_config(tmp_path, """\
            performance:
              request_timeout: 99.0
        """)
        assert cm.get("performance.request_timeout") == 99.0
        # Sibling key should still be the default
        assert cm.get("performance.max_context_turns") == 15

    def test_override_deep_nested_value(self, tmp_path):
        cm = make_config(tmp_path, """\
            session:
              exit_behavior:
                auto_save: true
        """)
        assert cm.get("session.exit_behavior.auto_save") is True
        # Siblings of exit_behavior should be preserved from defaults
        assert cm.get("session.exit_behavior.clear_terminal") is True

    def test_new_top_level_key(self, tmp_path):
        cm = make_config(tmp_path, """\
            custom:
              my_flag: hello
        """)
        assert cm.get("custom.my_flag") == "hello"

    def test_list_value_overrides_completely(self, tmp_path):
        cm = make_config(tmp_path, """\
            vault:
              ignore_folders:
                - custom_folder
        """)
        folders = cm.get("vault.ignore_folders")
        assert folders == ["custom_folder"]


# ---------------------------------------------------------------------------
# ConfigManager — get / set
# ---------------------------------------------------------------------------

class TestConfigManagerGetSet:
    def test_set_creates_nested_path(self, tmp_path):
        cm = make_config(tmp_path, "")
        cm.set("new.deep.key", 42)
        assert cm.get("new.deep.key") == 42

    def test_set_overwrites_existing(self, tmp_path):
        cm = make_config(tmp_path, "")
        cm.set("performance.request_timeout", 1.0)
        assert cm.get("performance.request_timeout") == 1.0

    def test_set_then_get_string(self, tmp_path):
        cm = make_config(tmp_path, "")
        cm.set("runtime.default_persona", "arch")
        assert cm.get("runtime.default_persona") == "arch"

    def test_get_returns_full_dict_for_section(self, tmp_path):
        cm = make_config(tmp_path, "")
        perf = cm.get("performance")
        assert isinstance(perf, dict)
        assert "request_timeout" in perf


# ---------------------------------------------------------------------------
# ConfigManager — save / reload round-trip
# ---------------------------------------------------------------------------

class TestConfigManagerSave:
    def test_save_and_reload(self, tmp_path):
        cm = make_config(tmp_path, "")
        cm.set("performance.request_timeout", 77.0)
        assert cm.save()
        # Reload fresh instance
        cm2 = ConfigManager(config_path=str(tmp_path / "config.yaml"))
        assert cm2.get("performance.request_timeout") == 77.0

    def test_save_returns_false_on_bad_path(self):
        cm = ConfigManager(config_path="/nonexistent_dir/bad_path/config.yaml")
        assert cm.save() is False


# ---------------------------------------------------------------------------
# is_safe_path
# ---------------------------------------------------------------------------

class TestIsSafePath:
    def test_safe_child_path(self, tmp_path):
        child = str(tmp_path / "subdir" / "file.md")
        assert is_safe_path(child, str(tmp_path)) is True

    def test_traversal_rejected(self, tmp_path):
        traversal = str(tmp_path / ".." / ".." / "etc" / "passwd")
        assert is_safe_path(traversal, str(tmp_path)) is False

    def test_exact_base_dir_is_safe(self, tmp_path):
        assert is_safe_path(str(tmp_path), str(tmp_path)) is True

    def test_sibling_dir_rejected(self, tmp_path):
        sibling = str(tmp_path.parent / "other_dir" / "file.md")
        assert is_safe_path(sibling, str(tmp_path)) is False


# ---------------------------------------------------------------------------
# convert_md_to_slack_mrkdwn
# ---------------------------------------------------------------------------

class TestConvertMdToSlackMrkdwn:
    def test_bold_conversion(self):
        assert convert_md_to_slack_mrkdwn("**hello**") == "*hello*"

    def test_heading_conversion(self):
        result = convert_md_to_slack_mrkdwn("## My Section")
        assert result == "*My Section*"

    def test_h1_conversion(self):
        result = convert_md_to_slack_mrkdwn("# Top Level")
        assert result == "*Top Level*"

    def test_code_block_language_stripped(self):
        md = "```python\ncode\n```"
        result = convert_md_to_slack_mrkdwn(md)
        assert "```python" not in result
        assert "```\ncode\n```" in result

    def test_channel_backtick_stripped(self):
        result = convert_md_to_slack_mrkdwn("`#general`")
        assert result == "#general"

    def test_mention_backtick_stripped(self):
        result = convert_md_to_slack_mrkdwn("`@samantha`")
        assert result == "@samantha"

    def test_plain_text_unchanged(self):
        text = "Just plain text here."
        assert convert_md_to_slack_mrkdwn(text) == text


class TestGetVersion:
    """Regression: the CLI banner, the FastAPI app/health endpoint, and
    app.py's --version flag each used to hardcode their own "vX.Y.Z" literal
    (three independent copies of pyproject.toml's version field), and drifted
    stale within days. get_version() is now the one place this is resolved."""

    def test_returns_a_dotted_version_string_when_installed(self):
        v = get_version()
        assert v == "dev" or v.count(".") >= 1

    def test_falls_back_to_dev_when_package_not_installed(self, monkeypatch):
        def raise_not_found(*a, **k):
            raise Exception("package not installed")

        monkeypatch.setattr(
            "importlib.metadata.version", raise_not_found
        )
        assert get_version() == "dev"


class TestIsLocalBackend:
    """Shared by the chat path (grounding mode, request-timeout selection)
    and the sub-agent path (its own request timeout) - declared once here
    so both stay in sync instead of drifting into two copies."""

    def test_ollama_prefix_is_local(self):
        assert is_local_backend("ollama/gemma2:9b") is True

    def test_cloud_prefixes_are_not_local(self):
        assert is_local_backend("gemini/gemini-3.6-flash") is False
        assert is_local_backend("anthropic/claude-sonnet-5") is False

    def test_localhost_api_base_is_local_regardless_of_prefix(self):
        assert is_local_backend("openai/gpt-5", "http://localhost:11434/v1") is True

    def test_empty_model_is_not_local(self):
        assert is_local_backend("") is False
