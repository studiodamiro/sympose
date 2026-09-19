"""
Unit tests for sympose.commands.CommandInterceptor.

`intercept` used to be one ~1100-line function with every command handler
nested inside it as a closure — mccabe flagged it at complexity 151. It was
restructured into a data-driven dispatch table over top-level `_cmd_*`
handlers (see commands.py's own module docstring), with the five most
complex handlers (`_cmd_history`, `_cmd_config`, `_cmd_model`,
`_cmd_vault_ops`, `_cmd_skills`) further split into per-case functions.
This file's original coverage was limited to the unknown-command helper and
the `/help` alias; the classes below cover every other route so a future
change to the dispatch table or a case-function has a real regression net,
not just a manual smoke test.
"""

from unittest.mock import MagicMock

import pytest

import sympose.commands as commands
from sympose.commands import CommandInterceptor


class _FakeSkill:
    def __init__(self, minimum_capability_tier=None):
        self.minimum_capability_tier = minimum_capability_tier


def _engine():
    engine = MagicMock()
    engine.pm.get_profile.return_value = {
        "handle": "samantha",
        "name": "Samantha",
        "model": "gpt-4o-mini",
        "skills": ["vault_read"],
    }
    engine.pm.profiles = {"samantha": {}, "rosalind": {}}
    engine.active_sessions = {}
    engine.config.get.side_effect = lambda k: {
        "session.exit_behavior.default_target": "both",
        "performance.resume_context_turns": 6,
        "performance.render_mode": "hybrid",
        "runtime.default_persona": "samantha",
    }.get(k, "both")
    engine.get_model_override.return_value = None
    return engine


def _run(engine, clean_input: str):
    gen = CommandInterceptor.intercept(engine, "samantha", clean_input)
    return None if gen is None else "".join(gen)


@pytest.fixture
def engine():
    return _engine()


@pytest.fixture
def no_console(monkeypatch):
    """Forces every handler's `TerminalUI.get_console()` branch to the
    plain-text (non-interactive) path, so assertions can check literal
    returned strings instead of a rendered terminal panel."""
    monkeypatch.setattr(commands.TerminalUI, "get_console", lambda: None)


class TestUnknownCommand:
    def test_unknown_slash_returns_helper_not_none(self, engine):
        out = _run(engine, "/confi")
        assert out is not None
        assert "Unknown command `/confi`" in out and "/commands" in out

    def test_helper_suggests_near_matches(self, engine):
        out = _run(engine, "/co")
        assert "/config" in out and "/compact" in out and "/commands" in out

    def test_unknown_with_no_near_match_still_points_at_commands(self, engine):
        out = _run(engine, "/zzz")
        assert out is not None and "Run `/commands`" in out

    def test_non_slash_input_passes_through(self, engine):
        assert _run(engine, "what did I write about grief") is None


class TestCommandsAlias:
    def test_commands_shows_the_help_reference(self, engine):
        out = _run(engine, "/commands")
        assert out is not None and "SYMPOSE HUB COMMANDS" in out

    def test_help_still_works(self, engine):
        out = _run(engine, "/help")
        assert out is not None and "SYMPOSE HUB COMMANDS" in out


class TestHistoryCommand:
    def test_new_starts_a_fresh_session(self, engine):
        out = _run(engine, "/history new")
        assert "fresh conversation session" in out
        engine.new_session.assert_called_once_with("samantha")

    def test_delete_found_session(self, engine, monkeypatch):
        monkeypatch.setattr(
            commands.SessionManager,
            "list_sessions",
            lambda limit=50: [{"session_id": "abc123"}],
        )
        monkeypatch.setattr(commands.SessionManager, "delete_session", lambda sid: True)
        out = _run(engine, "/history delete abc")
        assert "Deleted session `abc123`" in out

    def test_delete_not_found_session(self, engine, monkeypatch):
        monkeypatch.setattr(commands.SessionManager, "list_sessions", lambda limit=50: [])
        monkeypatch.setattr(commands.SessionManager, "delete_session", lambda sid: False)
        out = _run(engine, "/history delete zzz")
        assert "Could not delete session `zzz`" in out

    def test_view_not_found_session(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(commands.SessionManager, "list_sessions", lambda limit=50: [])
        monkeypatch.setattr(commands.SessionManager, "load_session", lambda sid: None)
        out = _run(engine, "/history view zzz")
        assert "Session `zzz` not found" in out

    def test_resume_missing_session(self, engine, no_console):
        engine.resume_session.return_value = None
        out = _run(engine, "/history resume zzz")
        assert "Session `zzz` not found" in out

    def test_list_with_no_sessions(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(
            commands.SessionManager,
            "list_sessions",
            lambda handle=None, limit=15, active_session_id=None: [],
        )
        out = _run(engine, "/history")
        assert "No past conversations found" in out


class TestResetAndClear:
    def test_reset_wipes_history(self, engine):
        out = _run(engine, "/reset")
        assert "Conversation history deleted" in out
        engine.reset_history.assert_called_once_with("samantha")

    def test_natural_language_reset_phrasing(self, engine):
        out = _run(engine, "please delete our chat")
        assert "Conversation history deleted" in out

    def test_clear_returns_sentinel(self, engine):
        assert _run(engine, "/clear") == "CLEARED_SESSION"

    def test_reset_memory_writes_template(self, engine, tmp_path):
        mem_file = tmp_path / "samantha_memory.md"
        engine.pm.get_profile.return_value = {
            "handle": "samantha",
            "name": "Samantha",
            "memory_file": str(mem_file),
        }
        out = _run(engine, "/reset memory")
        assert "memory and active conversation deleted" in out
        assert mem_file.exists()


class TestSaveCommand:
    def test_save_reports_success(self, engine):
        engine.summarize_session.return_value = {
            "status": "success",
            "targets_saved": ["memory"],
        }
        out = _run(engine, "/save")
        assert "Session Saved Successfully" in out
        assert "memory" in out

    def test_save_reports_failure(self, engine):
        engine.summarize_session.return_value = {
            "status": "error",
            "message": "nothing to save",
        }
        out = _run(engine, "/save")
        assert "nothing to save" in out


class TestConfigCommand:
    def test_show_lists_settings(self, engine):
        out = _run(engine, "/config")
        assert "ACTIVE RUNTIME CONFIGURATION" in out

    def test_get_known_key(self, engine):
        out = _run(engine, "/config get performance.max_context_turns")
        assert "performance.max_context_turns" in out

    def test_get_unknown_key(self, engine):
        out = _run(engine, "/config get not.a.real.key")
        assert "Unknown config key" in out

    def test_set_unknown_key(self, engine):
        out = _run(engine, "/config set not.a.real.key 5")
        assert "Unknown config key" in out

    def test_set_persona_scoped_key_rejected(self, engine):
        out = _run(engine, "/config set temperature 0.5")
        assert "per-persona" in out

    def test_set_valid_key_persists(self, engine):
        out = _run(engine, "/config set performance.max_context_turns 20")
        assert "persisted to disk" in out
        engine.config.set.assert_called_once_with("performance.max_context_turns", 20)
        engine.config.save.assert_called_once()
        assert engine.max_turns == 20


class TestPersonaCommand:
    def test_show_unknown_persona(self, engine):
        engine.pm.get_profile.side_effect = (
            lambda h: None if h == "ghost" else {"name": "Samantha"}
        )
        out = _run(engine, "/persona show @ghost")
        assert "not found" in out

    def test_show_lists_knobs(self, engine):
        engine.pm.get_profile.side_effect = lambda h: {"name": "Samantha"}
        out = _run(engine, "/persona show @samantha")
        assert "PER-PERSONA KNOBS" in out

    def test_set_delegates_to_profile_manager(self, engine):
        engine.pm.set_persona_field.return_value = (True, "temperature set to 0.5")
        out = _run(engine, "/persona set @samantha temperature 0.5")
        assert "temperature set to 0.5" in out
        engine.pm.set_persona_field.assert_called_once_with(
            "samantha", "temperature", "0.5"
        )


class TestRenderCommand:
    def test_valid_mode_persists(self, engine):
        out = _run(engine, "/render buffered")
        assert "render mode updated to **`buffered`**" in out
        engine.config.set.assert_called_once_with("performance.render_mode", "buffered")

    def test_invalid_mode_rejected(self, engine):
        out = _run(engine, "/render nonsense")
        assert "Invalid render mode" in out


class TestRememberCommand:
    def test_saves_fact(self, engine):
        engine.pm.append_memory.return_value = True
        out = _run(engine, "/remember I like tea")
        assert "Saved to Samantha's memory" in out
        assert "I like tea" in out

    def test_empty_fact_shows_usage(self, engine):
        out = _run(engine, "/remember ")
        assert "Usage:" in out


class TestCompactCommand:
    def test_compacts_shared_memory(self, engine, monkeypatch, tmp_path):
        import sympose.compactor as compactor_mod

        monkeypatch.setattr(compactor_mod.MemoryCompactor, "count_bullet_lines", lambda f: 3)
        monkeypatch.setattr(compactor_mod.MemoryCompactor, "compact_file", lambda f, is_shared: True)
        engine.pm.profiles_dir = str(tmp_path)
        out = _run(engine, "/compact shared")
        assert "Compacting Shared Team Working Memory" in out
        assert "Compaction Complete" in out

    def test_compacts_persona_memory(self, engine, monkeypatch):
        import sympose.compactor as compactor_mod

        monkeypatch.setattr(compactor_mod.MemoryCompactor, "count_bullet_lines", lambda f: 1)
        monkeypatch.setattr(compactor_mod.MemoryCompactor, "compact_file", lambda f, is_shared: False)
        out = _run(engine, "/compact")
        assert "Compacting Samantha's Working Memory" in out
        assert "Compaction failed" in out


class TestModelCommand:
    def test_status_shows_current_model(self, engine):
        out = _run(engine, "/model")
        assert "MODEL & PROVIDER CONFIGURATION" in out
        assert "gpt-4o-mini" in out

    def test_find_with_no_query_string_shows_usage(self):
        # Only reachable if `_model_find` is ever called with '' directly —
        # `_cmd_model` can't produce that itself, since a bare "/model find"
        # (no trailing query) falls through to the model-override branch
        # instead (matches "find" as a literal model id).
        out = "".join(commands._model_find(""))
        assert "Usage:" in out

    def test_bare_find_with_no_query_sets_model_override_instead(self, engine):
        # Documents that quirk: "/model find" alone is indistinguishable
        # from setting the override to a model literally named "find".
        out = _run(engine, "/model find")
        assert "temporarily set to `find`" in out

    def test_find_with_no_matches(self, engine, monkeypatch):
        monkeypatch.setattr(commands.ModelCatalog, "search_models", lambda q, limit=10: [])
        out = _run(engine, "/model find nonexistent-model-xyz")
        assert "No models found matching" in out

    def test_refresh_reports_count(self, engine, monkeypatch):
        monkeypatch.setattr(
            commands.ModelCatalog, "get_cached_models", lambda force_refresh=False: [1, 2, 3]
        )
        out = _run(engine, "/model refresh")
        assert "3 models indexed" in out

    def test_reset_clears_override(self, engine):
        out = _run(engine, "/model reset")
        assert "Reset model" in out
        engine.clear_model_override.assert_called_once_with("samantha")

    def test_set_switches_model(self, engine):
        out = _run(engine, "/model openrouter/anthropic/claude-3.5-sonnet")
        assert "temporarily" in out
        engine.set_model_override.assert_called_once_with(
            "samantha", "openrouter/anthropic/claude-3.5-sonnet"
        )

    def test_local_override_warns_when_vault_folders_configured(self, engine):
        engine.pm.get_profile.return_value = {
            "handle": "samantha",
            "name": "Samantha",
            "vault_folders": ["Journal"],
        }
        out = _run(engine, "/model ollama/gemma2:9b")
        assert "aren't second-guessed" in out

    def test_override_below_a_loaded_skills_capability_floor_warns(self, engine, monkeypatch):
        """ADR-139: a manual override was previously excluded from every
        capability-tier gate (ADR-128's sub-agent wiring, ADR-135's
        main-turn opt-in) — this is the one place that checks it."""
        engine.pm.get_profile.return_value = {
            "handle": "samantha",
            "name": "Samantha",
            "skills": ["vault_read"],
        }
        monkeypatch.setattr(
            commands.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(minimum_capability_tier="standard"),
        )
        monkeypatch.setattr(
            commands.config_manager,
            "get",
            lambda key, default=None: {
                "models.capability_tier_order": ["basic", "standard", "high"],
                "models.capability_tiers": {},
            }.get(key, default),
        )
        out = _run(engine, "/model ollama/gemma4:e4b")
        assert "is tier `basic`" in out
        assert "needs at least `standard`" in out

    def test_override_that_clears_the_floor_does_not_warn(self, engine, monkeypatch):
        engine.pm.get_profile.return_value = {
            "handle": "samantha",
            "name": "Samantha",
            "skills": ["vault_read"],
        }
        monkeypatch.setattr(
            commands.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(minimum_capability_tier="standard"),
        )
        monkeypatch.setattr(
            commands.config_manager,
            "get",
            lambda key, default=None: {
                "models.capability_tier_order": ["basic", "standard", "high"],
                "models.capability_tiers": {"gemini/gemini-3.6-flash": "high"},
            }.get(key, default),
        )
        out = _run(engine, "/model gemini/gemini-3.6-flash")
        assert "needs at least" not in out

    def test_no_loaded_skill_declares_a_floor_does_not_warn(self, engine, monkeypatch):
        engine.pm.get_profile.return_value = {
            "handle": "samantha",
            "name": "Samantha",
            "skills": ["web_search"],
        }
        monkeypatch.setattr(
            commands.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(minimum_capability_tier=None),
        )
        out = _run(engine, "/model ollama/gemma4:e4b")
        assert "needs at least" not in out


class TestVaultOpsCommand:
    def test_backlinks_digest(self, engine, monkeypatch):
        monkeypatch.setattr(
            commands.VaultManager, "get_backlinks_digest", lambda p, t: f"backlinks for {t}"
        )
        out = _run(engine, "/vault backlinks MyNote")
        assert out == "backlinks for MyNote"

    def test_backlinks_usage_with_no_target(self, engine):
        out = _run(engine, "/backlinks ")
        assert "Usage:" in out

    def test_open_in_obsidian(self, engine, monkeypatch):
        monkeypatch.setattr(
            commands.VaultManager, "open_in_obsidian", lambda p, t: (True, f"opened {t}")
        )
        out = _run(engine, "/open MyNote")
        assert "opened MyNote" in out

    def test_read_note_not_found(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(
            commands.VaultManager, "resolve_note_target", lambda p, t: (None, None)
        )
        out = _run(engine, "/read Missing")
        assert "not found in allowed vault folders" in out

    def test_read_note_renders_content(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(
            commands.VaultManager,
            "resolve_note_target",
            lambda p, t: ("MyNote.md", "/abs/MyNote.md"),
        )
        monkeypatch.setattr(commands.VaultManager, "read_note", lambda p, rel: "note body")
        monkeypatch.setattr(commands.VaultManager, "get_last_search", lambda p: [])
        out = _run(engine, "/read MyNote")
        assert "MyNote.md" in out and "note body" in out

    def test_no_previous_search(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(commands.VaultManager, "get_last_search", lambda p: [])
        out = _run(engine, "/vault")
        assert "No previous search results" in out

    def test_query_runs_structured_search(self, engine, monkeypatch, no_console):
        monkeypatch.setattr(commands.VaultManager, "get_last_search", lambda p: [])
        monkeypatch.setattr(
            commands.VaultManager, "search_structured", lambda p, q: [{"rel_path": "x.md"}]
        )
        monkeypatch.setattr(
            commands.VaultManager, "format_search_digest", lambda q, r: f"digest for {q}"
        )
        out = _run(engine, "/vault grief")
        assert out == "digest for grief"


class TestNoteAndDailyCommand:
    def test_note_requires_content(self, engine):
        out = _run(engine, "/note file.md")
        assert "Usage:" in out

    def test_note_writes(self, engine, monkeypatch):
        monkeypatch.setattr(commands.VaultManager, "write_note", lambda p, f, c: f"wrote {f}: {c}")
        out = _run(engine, "/note file.md hello world")
        assert out == "wrote file.md: hello world"

    def test_daily_requires_content(self, engine):
        out = _run(engine, "/daily ")
        assert "Usage:" in out

    def test_daily_writes(self, engine, monkeypatch):
        monkeypatch.setattr(commands.VaultManager, "write_daily_note", lambda p, c: f"daily: {c}")
        out = _run(engine, "/daily reflecting today")
        assert out == "daily: reflecting today"


class TestAskCommand:
    def test_unknown_persona(self, engine):
        engine.pm.get_profile.side_effect = (
            lambda h: None if h == "ghost" else {"name": "Samantha"}
        )
        out = _run(engine, "/ask @ghost do a thing")
        assert "not found" in out

    def test_delegates_to_persona(self, engine):
        engine.pm.get_profile.side_effect = lambda h: {"name": "Rosalind", "title": "Editor"}
        engine.consult_persona.return_value = iter(["Here's the answer."])
        out = _run(engine, "/ask @rosalind edit this")
        assert "Delegating to Rosalind" in out
        assert "Here's the answer." in out


class TestSkillsCommand:
    def test_show_unknown_skill(self, engine, monkeypatch):
        monkeypatch.setattr(commands.skill_manager, "get_skill", lambda name: None)
        out = _run(engine, "/skill show ghost_skill")
        assert "not found" in out

    def test_show_known_skill(self, engine, monkeypatch):
        skill = MagicMock(
            title="Vault Read",
            name="vault_read",
            description="reads the vault",
            filepath="skills/vault_read.md",
            content="playbook body",
            tags=[],
            mcp_servers=[],
            recommended_models=[],
        )
        skill.name = "vault_read"
        monkeypatch.setattr(commands.skill_manager, "get_skill", lambda n: skill)
        out = _run(engine, "/skill show vault_read")
        assert "VAULT READ" in out and "playbook body" in out

    def test_add_mounts_skill(self, engine, monkeypatch):
        monkeypatch.setattr(commands.skill_manager, "get_skill", lambda n: MagicMock())
        engine.pm.update_persona_skills.return_value = (True, "mounted")
        out = _run(engine, "/skill add vault_read")
        assert "mounted" in out
        engine.pm.update_persona_skills.assert_called_once_with(
            "samantha", "vault_read", action="add"
        )

    def test_remove_unmounts_skill(self, engine):
        engine.pm.update_persona_skills.return_value = (True, "unmounted")
        out = _run(engine, "/skill remove vault_read")
        assert "unmounted" in out
        engine.pm.update_persona_skills.assert_called_once_with(
            "samantha", "vault_read", action="remove"
        )

    def test_default_lists_all_skills(self, engine, monkeypatch):
        monkeypatch.setattr(commands.skill_manager, "list_skills", lambda: [])
        monkeypatch.setattr(commands.mcp_registry, "servers", {})
        out = _run(engine, "/skills")
        assert "INSTALLED SKILLS & MCP TOOL SERVERS" in out


class TestSubAgentCommand:
    def test_requires_task(self, engine):
        out = _run(engine, "/subagent vault_read")
        assert "Usage:" in out

    def test_dispatches_with_skills_and_mcp(self, engine, monkeypatch):
        monkeypatch.setattr(commands.skill_manager, "get_skill", lambda t: t == "vault_read" or None)
        monkeypatch.setattr(commands.mcp_registry, "servers", {"web_search": {}})
        monkeypatch.setattr(
            commands.SubAgentEngine,
            "execute_sub_agent_stream",
            lambda task: iter(["report"]),
        )
        out = _run(engine, "/subagent vault_read,web_search summarize the vault")
        assert "Dispatching Ephemeral Sub-Agent" in out
        assert "report" in out


class TestMentionDelegation:
    def test_known_handle_delegates(self, engine):
        engine.pm.get_profile.side_effect = lambda h: {"name": "Rosalind", "title": "Editor"}
        engine.consult_persona.return_value = iter(["chunk"])
        out = _run(engine, "@rosalind can you review this")
        assert "Delegating to Rosalind" in out
        assert "chunk" in out

    def test_unknown_handle_falls_through(self, engine):
        assert _run(engine, "@ghost hello") is None

    def test_self_mention_falls_through(self, engine):
        assert _run(engine, "@samantha hello") is None


class TestDeleteCommand:
    def test_cannot_delete_samantha(self, engine):
        out = _run(engine, "/delete @samantha")
        assert "cannot be deleted" in out

    def test_missing_persona_reports_not_found(self, engine, tmp_path):
        engine.pm.profiles_dir = str(tmp_path)
        out = _run(engine, "/delete @ghost")
        assert "not found" in out

    def test_archives_persona_files(self, engine, tmp_path):
        engine.pm.profiles_dir = str(tmp_path)
        (tmp_path / "curie.yaml").write_text("handle: curie\n")
        out = _run(engine, "/delete @curie")
        assert "Retired persona @curie" in out
        assert (tmp_path / "_archived" / "curie" / "curie.yaml").exists()
