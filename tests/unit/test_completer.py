"""
Unit tests for sympose.completer.SymposeCompleter — Tab completion routing.

`command_completions` (sympose/completer_rules.py) used to be one 34-branch
`if cmd == ...` ladder and had no coverage beyond the `/config` cases below;
it's now a dispatch table over per-command `_complete_*` functions (see that
module's own docstring). The classes further down add coverage for every
other command's completion branch.
"""

from unittest.mock import MagicMock

import pytest

from sympose.completer import SymposeCompleter


@pytest.fixture
def comp():
    return SymposeCompleter(MagicMock())


@pytest.fixture
def wired_comp(comp, monkeypatch):
    """A completer with its dynamic lookups stubbed to fixed lists — the
    bare `MagicMock()` engine underneath `comp` can't support real
    iteration over `.profiles.keys()` etc., and these branches only care
    about the completion logic, not persona/skill discovery itself."""
    monkeypatch.setattr(comp, "get_personas", lambda: ["@samantha", "@rosalind"])
    monkeypatch.setattr(comp, "get_skills", lambda: ["git_workflow", "vault_read"])
    monkeypatch.setattr(comp, "get_session_ids", lambda: ["abc123", "def456"])
    monkeypatch.setattr(
        comp, "get_sub_agent_targets", lambda: ["git_workflow", "web_search"]
    )
    return comp


def _c(comp, line, text):
    return comp.get_completions(line, text)


class TestRootCommands:
    @pytest.mark.parametrize("prefix,expected", [
        ("/back", "/backlinks"),
        ("/cl", "/cls"),
        ("/vau", "/vaults"),
    ])
    def test_missing_aliases_now_complete(self, comp, prefix, expected):
        assert expected in _c(comp, prefix, prefix)


class TestConfigCompletion:
    def test_bare_key_prefix_completes_leniently(self, comp):
        """`/config vau<TAB>` — the reported gap: no `set`/`get` typed yet."""
        out = _c(comp, "/config vau", "vau")
        assert out and all(k.startswith("vault.") for k in out)

    def test_first_arg_offers_subcommands(self, comp):
        out = _c(comp, "/config ", "")
        assert "get" in out and "set" in out

    def test_get_then_key(self, comp):
        out = _c(comp, "/config get vault.man", "vault.man")
        assert "vault.manifest.enabled" in out

    def test_set_then_key(self, comp):
        out = _c(comp, "/config set performance.str", "performance.str")
        assert "performance.stream" in out

    def test_value_position_is_not_offered_keys(self, comp):
        assert _c(comp, "/config set performance.stream tr", "tr") == []


class TestHistoryCompletion:
    def test_bare_offers_subcommands(self, wired_comp):
        out = _c(wired_comp, "/history ", "")
        assert "resume" in out and "delete" in out

    def test_resume_then_session_id(self, wired_comp):
        out = _c(wired_comp, "/history resume ", "")
        assert out == ["abc123", "def456"]

    def test_sessions_alias_behaves_the_same(self, wired_comp):
        out = _c(wired_comp, "/sessions ", "")
        assert "resume" in out


class TestPersonaHandleArgCommands:
    @pytest.mark.parametrize("cmd", ["/switch", "/delete", "/retire", "/ask"])
    def test_offers_persona_handles(self, wired_comp, cmd):
        out = _c(wired_comp, f"{cmd} ", "")
        assert out == ["@samantha", "@rosalind"]

    def test_matches_without_the_at_sign_too(self, wired_comp):
        out = _c(wired_comp, "/switch rosa", "rosa")
        assert out == ["@rosalind"]


class TestSubagentCompletion:
    def test_offers_skills_and_mcp_targets(self, wired_comp):
        out = _c(wired_comp, "/subagent ", "")
        assert out == ["git_workflow", "web_search"]


class TestSkillCompletion:
    def test_bare_offers_subcommands_and_skills(self, wired_comp):
        out = _c(wired_comp, "/skill ", "")
        assert "add" in out and "git_workflow" in out

    def test_add_offers_skill_names(self, wired_comp):
        out = _c(wired_comp, "/skill add ", "")
        assert out == ["git_workflow", "vault_read"]

    def test_add_skill_then_persona_handle(self, wired_comp):
        out = _c(wired_comp, "/skill add git_workflow @", "@")
        assert out == ["@samantha", "@rosalind"]

    def test_show_does_not_offer_persona_handle(self, wired_comp):
        # "show" isn't a mutating subcommand, so a trailing "@" isn't
        # reachable through the persona-arg branch.
        out = _c(wired_comp, "/skill show git_workflow @", "@")
        assert out == []

    def test_skills_and_tools_aliases_behave_the_same(self, wired_comp):
        assert "add" in _c(wired_comp, "/skills ", "")
        assert "add" in _c(wired_comp, "/tools ", "")


class TestVaultCompletion:
    def test_offers_subcommands(self, comp):
        out = _c(comp, "/vault ", "")
        assert set(out) == {"back", "list", "backlinks", "open", "read"}


class TestSaveCompletion:
    def test_offers_save_targets(self, comp):
        assert _c(comp, "/save ", "") == ["both", "memory", "obsidian"]


class TestRenderCompletion:
    def test_offers_render_modes(self, comp):
        assert _c(comp, "/render ", "") == ["hybrid", "buffered", "raw"]


class TestHelpCompletion:
    def test_bare_prefix_matches_the_unslashed_topic(self, comp):
        out = _c(comp, "/help conf", "conf")
        assert "config" in out

    def test_slashed_prefix_matches_the_slashed_topic(self, comp):
        out = _c(comp, "/help /conf", "/conf")
        assert "/config" in out


class TestPersonaCommandCompletion:
    def test_bare_offers_show_and_set(self, wired_comp):
        assert _c(wired_comp, "/persona ", "") == ["show", "set"]

    def test_show_offers_persona_handles(self, wired_comp):
        out = _c(wired_comp, "/persona show ", "")
        assert out == ["@samantha", "@rosalind"]

    def test_at_sign_offers_persona_handles_anywhere(self, wired_comp):
        out = _c(wired_comp, "/persona set @", "@")
        assert out == ["@samantha", "@rosalind"]

    def test_set_with_handle_offers_persona_keys(self, wired_comp):
        out = _c(wired_comp, "/persona set @samantha temp", "temp")
        assert any(k.startswith("temp") for k in out)


class TestCompactCompletion:
    def test_offers_shared_and_personas(self, wired_comp):
        out = _c(wired_comp, "/compact ", "")
        assert out == ["shared", "@samantha", "@rosalind"]


class TestModelCompletion:
    def test_find_offers_common_terms(self, comp):
        out = _c(comp, "/model find son", "son")
        assert out == ["sonnet"]

    def test_bare_offers_common_models(self, comp):
        out = _c(comp, "/model ", "")
        assert "list" in out and "reset" in out

    def test_openrouter_prefix_tries_dynamic_catalog(self, comp, monkeypatch):
        monkeypatch.setattr(
            "sympose.completer_rules.ModelCatalog.get_completion_candidates",
            lambda text: ["openrouter/anthropic/claude-3-opus"],
        )
        out = _c(comp, "/model openrouter/anthropic/claude-3-o", "openrouter/anthropic/claude-3-o")
        assert "openrouter/anthropic/claude-3-opus" in out

    def test_dynamic_catalog_failure_falls_back_to_static_list(self, comp, monkeypatch):
        monkeypatch.setattr(
            "sympose.completer_rules.ModelCatalog.get_completion_candidates",
            MagicMock(side_effect=RuntimeError("network down")),
        )
        out = _c(comp, "/model openrouter/", "openrouter/")
        assert out  # static COMMON_MODELS entries starting with "openrouter/"


class TestFallbacksAndUnknownCommands:
    def test_inline_mention_completes_personas(self, wired_comp):
        out = _c(wired_comp, "hey @rosa what do you think", "@rosa")
        assert out == ["@rosalind"]

    def test_unknown_command_returns_empty(self, comp):
        assert _c(comp, "/nonexistent-command ", "") == []
