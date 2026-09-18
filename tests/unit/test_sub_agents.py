"""
Unit tests for sympose.sub_agents.SubAgentEngine — the tool-loop budget backstop.

Regression: a sub-agent that read the relevant notes but then spent its remaining
tool turns on redundant greps hit `max_sub_agent_tool_turns` and returned
"reached maximum tool turns without completing final synthesis" — throwing away
the content it had already gathered. The final turn now disables tools and
forces a synthesis; if that still comes back empty, `_forced_synthesis` is the
backstop.
"""

import types

import pytest

from sympose import sub_agents
from sympose.sub_agents import SubAgentEngine, SubAgentTask, _resolve_target_model


class _FakeChoice:
    def __init__(self, content=None, tool_calls=None):
        self.message = types.SimpleNamespace(
            content=content,
            tool_calls=tool_calls,
            to_dict=lambda: {"role": "assistant", "content": content or ""},
        )


def _resp(content=None, tool_calls=None):
    return types.SimpleNamespace(choices=[_FakeChoice(content, tool_calls)])


def _fake_tool_call(name="read_file"):
    return types.SimpleNamespace(
        id="call_1",
        function=types.SimpleNamespace(
            name=name, arguments='{"path": "People/Tin.md"}'
        ),
    )


def _fake_tool_call_named(name, arguments_json):
    return types.SimpleNamespace(
        id="call_1",
        function=types.SimpleNamespace(name=name, arguments=arguments_json),
    )


@pytest.fixture
def ctx(monkeypatch):
    """Stub _build_sub_agent_context so no real MCP / model setup runs."""
    monkeypatch.setattr(
        SubAgentEngine,
        "_build_sub_agent_context",
        classmethod(
            lambda cls, task: (
                "sys",
                "gemini/gemini-3.6-flash",
                [{"role": "user", "content": task.task_prompt}],
                {},
                {},
                [{"type": "function", "function": {"name": "read_file"}}],
                ["/vault"],
                {"handle": task.parent_agent},
            )
        ),
    )
    monkeypatch.setattr(
        SubAgentEngine,
        "_dispatch_tool_call",
        staticmethod(
            lambda tc, t2c, dirs, profile=None: (
                "call_1",
                "read_file",
                "path=People/Tin.md",
                True,
                "note body: Tin is Dylan's mother.",
                {"path": "People/Tin.md"},
            )
        ),
    )
    monkeypatch.setattr(
        SubAgentEngine, "_inject_api_key", staticmethod(lambda kw, m: None)
    )


def test_budget_exhaustion_forces_synthesis_instead_of_failure(ctx, monkeypatch):
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        # No tools passed on the final turn -> that's the forced-synthesis call.
        if "tools" not in kwargs:
            return _resp(content="Tin is Dylan's mother; you noted you miss her.")
        return _resp(tool_calls=[_fake_tool_call()])

    monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)

    task = SubAgentTask(task_prompt="find notes on Tin and Dylan", max_tool_turns=4)
    out, tool_calls = SubAgentEngine.execute_sub_agent_task(task)

    assert "Tin is Dylan's mother" in out
    assert "maximum tool turns" not in out
    assert len(tool_calls) == 3  # turns 1-3 tool-called; turn 4 was tools-off synthesis


def test_normal_completion_unaffected(ctx, monkeypatch):
    def fake_completion(**kwargs):
        return _resp(content="done: the answer")

    monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
    out, _ = SubAgentEngine.execute_sub_agent_task(
        SubAgentTask(task_prompt="x", max_tool_turns=8)
    )
    assert out == "done: the answer"


def test_forced_synthesis_empty_falls_back_to_notice(ctx, monkeypatch):
    def fake_completion(**kwargs):
        if "tools" not in kwargs:
            return _resp(content="")  # forced synth yields nothing
        return _resp(tool_calls=[_fake_tool_call()])

    monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
    out, _ = SubAgentEngine.execute_sub_agent_task(
        SubAgentTask(task_prompt="x", max_tool_turns=3)
    )
    assert "tool budget" in out


class TestBuildSubAgentContextPersonaMemory:
    """Regression: a sub-agent spawned to recall "our favorite game" had no
    access to the parent persona's working memory, which already spelled out
    exactly what that meant - it was left to reconstruct the meaning from
    scratch via blind grep/find, wandered outside the vault, and still
    returned a guessed, mismatched note. `_build_sub_agent_context` must now
    fold the parent's working memory into the sub-agent's system prompt."""

    @staticmethod
    def _task(skills=None):
        return SubAgentTask(
            task_prompt="favorite game", skills=skills or [], parent_agent="samantha"
        )

    def test_parent_persona_memory_reaches_the_system_prompt(self, monkeypatch):
        class FakeProfileManager:
            def get_profile(self, handle):
                return {"handle": handle, "memory_file": "mem.md"}

            def get_persona_memory(self, profile):
                return "Favorite game is Vault Roulette."

        monkeypatch.setattr("sympose.sub_agents.ProfileManager", FakeProfileManager)
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_allowed_dirs",
            staticmethod(lambda p: ["/vault"]),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.skill_manager.format_skills_for_prompt",
            lambda skills: "",
        )

        system_prompt, *_ = SubAgentEngine._build_sub_agent_context(self._task())
        assert "Favorite game is Vault Roulette." in system_prompt

    def test_no_memory_block_when_parent_has_none(self, monkeypatch):
        class FakeProfileManager:
            def get_profile(self, handle):
                return {"handle": handle, "memory_file": "mem.md"}

            def get_persona_memory(self, profile):
                return ""

        monkeypatch.setattr("sympose.sub_agents.ProfileManager", FakeProfileManager)
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_allowed_dirs",
            staticmethod(lambda p: ["/vault"]),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.skill_manager.format_skills_for_prompt",
            lambda skills: "",
        )

        system_prompt, *_ = SubAgentEngine._build_sub_agent_context(self._task())
        assert "Parent Persona's Working Memory" not in system_prompt

    def test_memory_is_appended_after_skills_text(self, monkeypatch):
        """Placed last, same "lost in the middle" reasoning as
        build_system_prompt's own persona-memory placement."""

        class FakeProfileManager:
            def get_profile(self, handle):
                return {"handle": handle, "memory_file": "mem.md"}

            def get_persona_memory(self, profile):
                return "MEMFACT"

        monkeypatch.setattr("sympose.sub_agents.ProfileManager", FakeProfileManager)
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_allowed_dirs",
            staticmethod(lambda p: ["/vault"]),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.skill_manager.format_skills_for_prompt",
            lambda skills: "SKILLTEXT",
        )

        system_prompt, *_ = SubAgentEngine._build_sub_agent_context(self._task())
        assert system_prompt.index("MEMFACT") > system_prompt.index("SKILLTEXT")


class TestOnProgressCallback:
    """The live terminal-status side-channel: fired the instant each tool
    call completes, not just once the whole multi-turn loop finishes."""

    def test_called_once_per_tool_call_with_the_same_summary_string(
        self, ctx, monkeypatch
    ):
        calls_seen = {"n": 0}

        def fake_completion(**kwargs):
            calls_seen["n"] += 1
            if "tools" not in kwargs:
                return _resp(content="done")
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)

        seen: list[str] = []
        task = SubAgentTask(task_prompt="x", max_tool_turns=2)
        out, tool_calls = SubAgentEngine.execute_sub_agent_task(
            task, on_progress=seen.append
        )

        assert seen == tool_calls
        assert seen == ["read_file(path=People/Tin.md)"]

    def test_not_called_when_no_tool_calls_happen(self, ctx, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.litellm.completion",
            lambda **kw: _resp(content="no tools needed"),
        )
        seen: list[str] = []
        SubAgentEngine.execute_sub_agent_task(
            SubAgentTask(task_prompt="x", max_tool_turns=3), on_progress=seen.append
        )
        assert seen == []

    def test_a_raising_callback_does_not_break_the_loop(self, ctx, monkeypatch):
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content="done anyway")
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)

        def boom(_):
            raise RuntimeError("terminal went away")

        out, _ = SubAgentEngine.execute_sub_agent_task(
            SubAgentTask(task_prompt="x", max_tool_turns=3), on_progress=boom
        )
        assert out == "done anyway"


# --------------------------------------------------------------------------- #
#  _dispatch_tool_call — native tools, MCP tools, unregistered tools, parsing #
# --------------------------------------------------------------------------- #


class _FakeMCPClient:
    def __init__(self, ok=True, result="mcp tool output"):
        self._ok, self._result = ok, result
        self.calls = []

    def call_tool(self, name, args):
        self.calls.append((name, args))
        return self._ok, self._result


def _tc(name, arguments, call_id="call_1"):
    """A litellm-style tool_call object (attribute access, not dict)."""
    return types.SimpleNamespace(
        id=call_id,
        function=types.SimpleNamespace(name=name, arguments=arguments),
    )


class TestDispatchToolCall:
    def test_native_tool_routes_to_native_tools_execute(self, monkeypatch):
        captured = {}

        def fake_execute(tool_name, args, allowed_dirs=None):
            captured.update(tool_name=tool_name, args=args, allowed_dirs=allowed_dirs)
            return True, "file contents"

        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute", staticmethod(fake_execute)
        )
        call_id, name, arg_summary, ok, res, _args = SubAgentEngine._dispatch_tool_call(
            _tc("read_file", '{"path": "People/Tin.md"}'), {}, ["/vault"]
        )
        assert (call_id, name, ok, res) == (
            "call_1",
            "read_file",
            True,
            "file contents",
        )
        assert arg_summary == "path=People/Tin.md"
        assert captured == {
            "tool_name": "read_file",
            "args": {"path": "People/Tin.md"},
            "allowed_dirs": ["/vault"],
        }

    def test_mcp_tool_routes_to_its_registered_client(self, monkeypatch):
        client = _FakeMCPClient(ok=True, result="42")
        _, name, _, ok, res, _args = SubAgentEngine._dispatch_tool_call(
            _tc("calc_add", '{"a": 1, "b": 41}'), {"calc_add": client}, None
        )
        assert (name, ok, res) == ("calc_add", True, "42")
        assert client.calls == [("calc_add", {"a": 1, "b": 41})]

    def test_unregistered_tool_fails_cleanly(self):
        _, name, _, ok, res, _args = SubAgentEngine._dispatch_tool_call(
            _tc("mystery_tool", "{}"), {}, None
        )
        assert ok is False
        assert "not registered" in res

    def test_malformed_json_arguments_become_empty_dict(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute",
            staticmethod(
                lambda tool_name, args, allowed_dirs=None: (
                    captured.update(args=args) or (True, "ok")
                )
            ),
        )
        SubAgentEngine._dispatch_tool_call(
            _tc("run_command", "not valid json"), {}, None
        )
        assert captured["args"] == {}

    def test_dict_style_tool_call_is_also_accepted(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute",
            staticmethod(lambda tool_name, args, allowed_dirs=None: (True, "ok")),
        )
        tc = {
            "id": "call_9",
            "function": {"name": "run_command", "arguments": '{"command": "ls"}'},
        }
        call_id, name, arg_summary, ok, res, _args = SubAgentEngine._dispatch_tool_call(
            tc, {}, None
        )
        assert (call_id, name, arg_summary, ok, res) == (
            "call_9",
            "run_command",
            "command=ls",
            True,
            "ok",
        )

    def test_long_output_is_truncated(self, monkeypatch):
        from sympose.sub_agents import MAX_TOOL_OUTPUT_CHARS

        huge = "x" * (MAX_TOOL_OUTPUT_CHARS + 500)
        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute",
            staticmethod(lambda tool_name, args, allowed_dirs=None: (True, huge)),
        )
        *_, res, _args = SubAgentEngine._dispatch_tool_call(_tc("read_file", "{}"), {}, None)
        assert len(res) < len(huge)
        assert res.endswith("[Output truncated for brevity]...")

    def test_arg_summary_only_includes_whitelisted_keys(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute",
            staticmethod(lambda tool_name, args, allowed_dirs=None: (True, "ok")),
        )
        _, _, arg_summary, _, _, _args = SubAgentEngine._dispatch_tool_call(
            _tc("run_command", '{"command": "ls", "unrelated_flag": true}'), {}, None
        )
        assert arg_summary == "command=ls"


# --------------------------------------------------------------------------- #
#  _inject_api_key                                                            #
# --------------------------------------------------------------------------- #


class TestInjectApiKey:
    @pytest.mark.parametrize(
        "prefix,env_var,model",
        [
            ("GEMINI_API_KEY", "GEMINI_API_KEY", "gemini/gemini-3.6-flash"),
            ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "anthropic/claude-sonnet-5"),
            ("OPENAI_API_KEY", "OPENAI_API_KEY", "openai/gpt-5"),
            ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY", "openrouter/x/y"),
        ],
    )
    def test_injects_matching_provider_key(self, monkeypatch, prefix, env_var, model):
        monkeypatch.setenv(env_var, "secret-123")
        kwargs = {}
        SubAgentEngine._inject_api_key(kwargs, model)
        assert kwargs["api_key"] == "secret-123"

    def test_no_key_injected_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        kwargs = {}
        SubAgentEngine._inject_api_key(kwargs, "gemini/gemini-3.6-flash")
        assert "api_key" not in kwargs

    def test_no_key_injected_for_local_ollama_model(self, monkeypatch):
        kwargs = {}
        SubAgentEngine._inject_api_key(kwargs, "ollama/gemma2:9b")
        assert "api_key" not in kwargs


class TestInjectTimeout:
    """Live bug: a sub-agent's litellm call had no `timeout` kwarg at all,
    surfacing as "litellm.Timeout: Connection timed out after None
    seconds" once the underlying connection genuinely stalled - the "None"
    is the tell that nothing real was ever configured for this call."""

    def test_sets_a_real_timeout_value(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.config_manager.get",
            lambda key, default=None: 42.0 if key == "sub_agent.request_timeout" else default,
        )
        kwargs = {}
        SubAgentEngine._inject_timeout(kwargs)
        assert kwargs["timeout"] == 42.0

    def test_uses_its_own_key_not_the_chat_paths_local_cloud_split(self, monkeypatch):
        # A sub-agent's report is delivered as one block once its whole
        # tool-calling loop finishes - no TTFT reason to use the short
        # cloud chat timeout, even when its own model is a cloud one.
        seen_keys = []

        def fake_get(key, default=None):
            seen_keys.append(key)
            return 99.0

        monkeypatch.setattr("sympose.sub_agents.config_manager.get", fake_get)
        kwargs = {}
        SubAgentEngine._inject_timeout(kwargs)
        assert seen_keys == ["sub_agent.request_timeout"]
        assert kwargs["timeout"] == 99.0


# --------------------------------------------------------------------------- #
#  execute_sub_agent_stream — the streaming twin of execute_sub_agent_task          #
# --------------------------------------------------------------------------- #


class TestExecuteSubAgentStream:
    def test_yields_tool_call_status_then_final_answer(self, ctx, monkeypatch):
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content="Tin is Dylan's mother.")
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="find notes on Tin", max_tool_turns=4)
        chunks = list(SubAgentEngine.execute_sub_agent_stream(task))

        assert any("Sub-agent calling tool" in c and "read_file" in c for c in chunks)
        assert chunks[-1] == "Tin is Dylan's mother."

    def test_budget_exhaustion_forces_synthesis(self, ctx, monkeypatch):
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content="synthesised from what was gathered")
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="x", max_tool_turns=3)
        chunks = list(SubAgentEngine.execute_sub_agent_stream(task))
        assert chunks[-1] == "synthesised from what was gathered"

    def test_warns_when_an_mcp_server_fails_to_connect(self, monkeypatch):
        monkeypatch.setattr(
            SubAgentEngine,
            "_build_sub_agent_context",
            classmethod(
                lambda cls, task: (
                    "sys",
                    "gemini/gemini-3.6-flash",
                    [{"role": "user", "content": task.task_prompt}],
                    {},  # no active_clients — "docs" never connected
                    {},
                    [],
                    None,
                    None,
                )
            ),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.litellm.completion",
            lambda **kwargs: _resp(content="done"),
        )
        task = SubAgentTask(task_prompt="x", mcp_servers=["docs"], max_tool_turns=2)
        chunks = list(SubAgentEngine.execute_sub_agent_stream(task))
        assert any(
            "Could not connect to MCP server" in c and "docs" in c for c in chunks
        )

    def test_execution_error_yields_a_warning_instead_of_raising(
        self, ctx, monkeypatch
    ):
        def raise_error(**kwargs):
            raise RuntimeError("model unavailable")

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", raise_error)
        task = SubAgentTask(task_prompt="x", max_tool_turns=2)
        chunks = list(SubAgentEngine.execute_sub_agent_stream(task))
        assert any("Sub-Agent Execution Error" in c for c in chunks)


# --------------------------------------------------------------------------- #
#  _content_unread / _swap_in_unread_note — catching a sub-agent that names   #
#  or quotes a note it never actually loaded via a successful read_file call. #
#  Live bug: asked to pull a random note and read it, gemma4:e4b burned its   #
#  whole tool budget on redundant grep/find attempts, never called            #
#  read_file, then (on a run that didn't honestly admit it) would have been   #
#  free to narrate invented content for whatever path it had merely found.    #
# --------------------------------------------------------------------------- #


class TestContentUnread:
    def test_no_path_named_is_silent(self):
        assert SubAgentEngine._content_unread("just some prose, no path", set()) is None

    def test_bare_backtick_filename_with_no_folder_prefix_is_caught(self):
        """Live bug: a real ollama/gemma4:e4b run cited its invented note as
        `2022-08-29.md` and **2022-08-29.md** - no folder prefix, so
        VAULT_PATH_TOKEN_RE alone (which requires one) missed it entirely
        and let the fabrication through untouched."""
        offending = SubAgentEngine._content_unread(
            "The random note is `2022-08-29.md`.\n\n**2022-08-29.md**\n\nFake body.",
            set(),
        )
        assert offending == "2022-08-29.md"

    def test_bare_filename_actually_read_via_run_command_is_not_flagged(self):
        """A sub-agent that reads a file with `cat` (or `sed`/`head`/an
        inline script) instead of the dedicated read_file tool genuinely did
        read it - `read_paths` isn't limited to read_file's own path arg."""
        assert (
            SubAgentEngine._content_unread(
                "The note `2022-08-29.md` says: real content here.",
                {"2022-08-29.md"},
            )
            is None
        )

    def test_path_named_but_never_read_is_flagged(self):
        offending = SubAgentEngine._content_unread(
            "The note Daily/2024/01-January/2024-01-01.md reads: 'Today was good.'",
            set(),
        )
        assert offending == "2024-01-01.md"

    def test_path_named_and_actually_read_is_not_flagged(self):
        assert (
            SubAgentEngine._content_unread(
                "The note Daily/2024/01-January/2024-01-01.md reads: 'Today was good.'",
                {"Daily/2024/01-January/2024-01-01.md"},
            )
            is None
        )

    def test_matching_is_case_insensitive_and_basename_only(self):
        """A read_file call given an absolute path shouldn't fail to match a
        reply that names the same file by its vault-relative form."""
        assert (
            SubAgentEngine._content_unread(
                "See Thoughts/MOUNTAIN.md for the full entry.",
                {"/Users/x/garden/Thoughts/mountain.md"},
            )
            is None
        )

    def test_one_of_several_named_paths_read_is_not_flagged(self):
        """Conservative by design: a synthesis correctly quoting one real
        note while merely mentioning another in passing isn't the
        fabrication shape this guards against - only flag when NONE of the
        named paths were actually read."""
        text = (
            "Read Daily/2024/01-January/2024-01-01.md; related to "
            "Thoughts/Mountain.md."
        )
        assert SubAgentEngine._content_unread(text, {"Daily/2024/01-January/2024-01-01.md"}) is None

    def test_same_named_note_in_different_folder_is_still_flagged(self):
        """C7: comparing by bare basename let a citation to a note in one
        folder incorrectly pass just because a same-named note in a
        *different* folder was actually read - a real cross-folder
        collision, not a hypothetical one, given the same filename showing
        up in more than one vault folder is unremarkable (e.g. every
        project keeping its own README.md)."""
        offending = SubAgentEngine._content_unread(
            "Per Projects/Foo.md, the answer is yes.",
            {"Archive/Foo.md"},
        )
        assert offending == "foo.md"

    def test_absolute_read_path_still_matches_relative_citation(self):
        """_path_tail_match must keep tolerating an absolute read_file path
        against a vault-relative citation of the same file (see
        test_matching_is_case_insensitive_and_basename_only above) even
        after the folder-qualified comparison stopped being basename-only -
        the fix is comparing more trailing segments, not requiring an exact
        whole-string match."""
        assert (
            SubAgentEngine._content_unread(
                "See Thoughts/Mountain.md for the full entry.",
                {"/Users/x/garden/Thoughts/Mountain.md"},
            )
            is None
        )


class TestSwapInUnreadNote:
    def test_swaps_in_the_real_note_when_it_resolves(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "Actual body text of the real note."),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        out = SubAgentEngine._swap_in_unread_note("2024-01-01.md", task)
        assert out.startswith("That's not what I actually have")
        assert "Actual body text of the real note." in out

    def test_falls_back_to_honest_admission_when_note_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(
                lambda profile, name: f"Note `{name}` not found in allowed vault folders."
            ),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        out = SubAgentEngine._swap_in_unread_note("ghost.md", task)
        assert "never actually opened it" in out
        assert "not found" not in out

    def test_falls_back_when_parent_profile_is_missing(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: None),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="nobody")
        out = SubAgentEngine._swap_in_unread_note("2024-01-01.md", task)
        assert "never actually opened it" in out


# --------------------------------------------------------------------------- #
#  _content_unsupported / _swap_in_unsupported — catching a sub-agent that    #
#  draws a confident conclusion with no verbatim trace back to anything it    #
#  actually retrieved, without ever naming a specific note - the prose-only   #
#  shape `_content_unread` deliberately leaves uncovered (its own docstring   #
#  calls this out). Live example: "Of course I remember - our favorite game   #
#  is X" stitched from real search/read hits but never quoting any of them.   #
# --------------------------------------------------------------------------- #

_LONG_UNRELATED_REPLY = (
    "Of course I remember our favorite game is random note discovery where "
    "we pick something unexpected from your vault and talk through whatever "
    "themes or feelings come up together as we go along today"
)


class TestContentUnsupported:
    def test_no_retrieval_attempted_is_silent(self):
        """No retrieval-shaped tool call this turn at all - purely
        conversational, nothing to judge against."""
        assert (
            SubAgentEngine._content_unsupported(_LONG_UNRELATED_REPLY, [], False) is False
        )

    def test_short_reply_is_silent_even_with_no_overlap(self):
        assert (
            SubAgentEngine._content_unsupported(
                "Sure, let's do another round.",
                ["note body: Tin is Dylan's mother."],
                True,
            )
            is False
        )

    def test_substantive_reply_with_no_overlap_is_flagged(self):
        assert (
            SubAgentEngine._content_unsupported(
                _LONG_UNRELATED_REPLY, ["note body: Tin is Dylan's mother."], True
            )
            is True
        )

    def test_substantive_reply_quoting_the_retrieved_content_is_not_flagged(self):
        reply = (
            "Here's what I actually found this turn, quoting it exactly: "
            "'note body: Tin is Dylan's mother.' It's a short but clear entry "
            "about your family, worth sitting with for a while longer."
        )
        assert (
            SubAgentEngine._content_unsupported(
                reply, ["note body: Tin is Dylan's mother."], True
            )
            is False
        )

    def test_short_source_content_verbatim_quoted_is_not_flagged(self):
        """Live bug (2026-09-17, found by /code-review): a fixed 4-word
        shingle made any source shorter than 4 words structurally
        unmatchable - `isdisjoint` against an always-empty shingle set is
        always True - so a reply correctly quoting a short note verbatim
        still got flagged as unsupported. Shingle size now adapts down to
        the shorter side's word count."""
        reply = (
            "I checked and your vault says, verbatim: 'Favorite game: chess.' "
            "That's the exact line from the note you asked about, word for word."
        )
        assert (
            SubAgentEngine._content_unsupported(
                reply, ["Favorite game: chess."], True
            )
            is False
        )

    def test_short_source_content_not_quoted_is_still_flagged(self):
        """Same short-source case, but the reply invents something the short
        source never said - the adaptive shingle size shouldn't make this
        any more permissive than the fixed-size version was."""
        reply = (
            _LONG_UNRELATED_REPLY  # shares no words with the short source below
        )
        assert (
            SubAgentEngine._content_unsupported(
                reply, ["Favorite game: chess."], True
            )
            is True
        )

    def test_retrieval_attempted_but_nothing_external_gathered_is_flagged(self):
        """The "echo laundering" case one level up: a retrieval-shaped tool
        call happened this turn, but everything it returned got excluded
        from `tool_outputs` (e.g. `_register_read` classified it as
        self-authored) - `tool_outputs` ends up empty, same as "nothing
        attempted," but `retrieval_attempted` tells them apart. A confident,
        substantive claim with zero real evidence is exactly the case that
        must still be caught, not silently waved through."""
        assert (
            SubAgentEngine._content_unsupported(_LONG_UNRELATED_REPLY, [], True) is True
        )

    def test_short_reply_below_shingle_size_is_not_a_false_positive(self, monkeypatch):
        """Tier-4 audit fix: the shingle size only ever clamped against the
        source side, contradicting the docstring's claimed "whichever side
        has fewer words" - unreachable under the default min_words (15,
        already bigger than _SHINGLE_SIZE's 4), so this lowers min_words to
        exercise it directly. A 3-word reply against the old code: shingle
        size stays 4 (clamped only to the longer source), _shingles' own
        len(words) < n guard then returns an *empty* set for the reply side,
        and an empty set is disjoint from everything - a genuine verbatim
        3-word run gets flagged as unsupported purely because it's shorter
        than the shingle size, not because it lacks any real overlap."""
        monkeypatch.setattr(
            "sympose.sub_agents.config_manager.get",
            lambda key, default=None: 1
            if key == "sub_agent.unsupported_synthesis_min_words"
            else default,
        )
        assert (
            SubAgentEngine._content_unsupported(
                "Chess is fun", ["note body: chess is fun and endlessly deep"], True
            )
            is False
        )


class TestSwapInUnsupported:
    def test_returns_the_raw_retrieved_material(self):
        out = SubAgentEngine._swap_in_unsupported(
            ["note body: Tin is Dylan's mother."]
        )
        assert "isn't actually backed by anything" in out
        assert "note body: Tin is Dylan's mother." in out

    def test_combines_multiple_outputs_and_truncates_when_oversized(self):
        from sympose.sub_agents import MAX_TOOL_OUTPUT_CHARS

        out = SubAgentEngine._swap_in_unsupported(["a" * (MAX_TOOL_OUTPUT_CHARS + 500)])
        assert "truncated" in out
        assert len(out) < MAX_TOOL_OUTPUT_CHARS + 500


class TestFinalizeSynthesis:
    """Live bug (2026-09-17, found by /code-review): a plain `if
    _content_unread: ... elif _content_unsupported: ...` let a content-free
    'I never opened it' recovery win even when real tool_outputs material
    from the same turn would have made a strictly better answer.
    `_finalize_synthesis` is the shared, ordering-aware helper both
    execution methods now call."""

    def test_unresolved_citation_prefers_real_tool_outputs_over_bare_apology(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "Note `ghost.md` not found in allowed vault folders."),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        text = "The note `ghost.md` says something relevant."
        out = SubAgentEngine._finalize_synthesis(
            text, set(), ["real snippet from vault_search"], True, task
        )
        assert "isn't actually backed by anything" in out
        assert "real snippet from vault_search" in out
        assert "never actually opened it" not in out

    def test_unresolved_citation_with_no_tool_outputs_falls_back_to_bare_apology(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "Note `ghost.md` not found in allowed vault folders."),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        text = "The note `ghost.md` says something relevant."
        out = SubAgentEngine._finalize_synthesis(text, set(), [], True, task)
        assert "never actually opened it" in out

    def test_resolved_citation_wins_regardless_of_tool_outputs(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "The real note body."),
        )
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        text = "The note `real.md` says something relevant."
        out = SubAgentEngine._finalize_synthesis(
            text, set(), ["unrelated real snippet"], True, task
        )
        assert "The real note body." in out
        assert "unrelated real snippet" not in out

    def test_no_citation_falls_through_to_unsupported_check(self):
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        out = SubAgentEngine._finalize_synthesis(
            _LONG_UNRELATED_REPLY, set(), ["note body: Tin is Dylan's mother."], True, task
        )
        assert "isn't actually backed by anything" in out

    def test_nothing_flagged_returns_original_synthesis_untouched(self):
        task = SubAgentTask(task_prompt="x", parent_agent="samantha")
        out = SubAgentEngine._finalize_synthesis(
            "Sure, let's do another round.", set(), [], False, task
        )
        assert out == "Sure, let's do another round."


class TestExecuteSubAgentTaskCatchesUnsupportedSynthesis:
    """End-to-end through execute_sub_agent_task: a long, confident synthesis
    with no verbatim tie to what was actually retrieved gets overridden -
    even when it never names a specific note for `_content_unread` to catch."""

    def test_unsupported_conclusion_gets_swapped_for_raw_material(self, ctx, monkeypatch):
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content=_LONG_UNRELATED_REPLY)
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="what's our favorite game?", max_tool_turns=4)
        out, _ = SubAgentEngine.execute_sub_agent_task(task)

        assert "random note discovery" not in out
        assert "note body: Tin is Dylan's mother." in out

    def test_grounded_conclusion_quoting_the_retrieval_is_untouched(self, ctx, monkeypatch):
        reply = (
            "Here's what I actually found this turn, quoting it exactly: "
            "'note body: Tin is Dylan's mother.' It's a short but clear entry "
            "about your family, worth sitting with for a while longer."
        )

        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content=reply)
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="what's our favorite game?", max_tool_turns=4)
        out, _ = SubAgentEngine.execute_sub_agent_task(task)
        assert out == reply


# --------------------------------------------------------------------------- #
#  The "echo laundering" loophole - live bug (2026-09-17, gemma4:e4b): a      #
#  successful run_command whose output is just the model's own invented text #
#  (e.g. `echo "I found two mentions of..."`) used to count as grounding     #
#  evidence for `_content_unsupported`, letting a fabrication "cite" itself   #
#  as its own source. `_register_read`'s `tool_outputs` param now only       #
#  accepts externally-sourced tool results.                                   #
# --------------------------------------------------------------------------- #


class TestRegisterReadToolOutputsLaundering:
    def test_echo_with_no_real_filename_is_excluded_from_tool_outputs(self):
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": 'echo "I found two mentions of getting old in your vault"'},
            'I found two mentions of getting old in your vault',
            set(),
            outputs,
        )
        assert outputs == []

    def test_chained_command_hiding_an_echo_is_still_excluded(self):
        """Tier-4 audit fix (round three of the same bug): checking only the
        whole command's own first word let `ls; echo fake stuff` slip past,
        since the *string's* first word is "ls", not "echo" - the echo is
        just chained behind an allowlisted no-op. Every top-level command in
        the chain must be checked, not just the first."""
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": 'ls; echo "According to notes/foo.md, the answer is yes"'},
            "According to notes/foo.md, the answer is yes",
            set(),
            outputs,
        )
        assert outputs == []

    def test_cat_of_a_real_file_is_included_in_tool_outputs(self, monkeypatch):
        """Tier-4 structural redesign: a run_command's output only counts
        once it's confirmed against the real file's own content, so this
        now needs a profile and a real (stubbed) read_note to back it -
        matching a genuine `cat` of an existing file, not just its
        filename appearing in the command text."""
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "real file content, and more"),
        )
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "cat /Users/x/garden/Daily/2022-08-29.md"},
            "real file content",
            set(),
            outputs,
            {"handle": "t"},
        )
        assert outputs == ["real file content"]

    def test_read_file_is_included_in_tool_outputs(self):
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "read_file", True, {"path": "Daily/2022-08-29.md"}, "real content", set(), outputs
        )
        assert outputs == ["real content"]

    def test_vault_search_snippets_are_included_in_tool_outputs(self):
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "vault_search",
            True,
            {"query": "aliens"},
            "**[1] `Daily/2022-08-29.md`** - ...snippet...",
            set(),
            outputs,
        )
        assert outputs == ["**[1] `Daily/2022-08-29.md`** - ...snippet..."]

    def test_a_failed_call_registers_no_output(self):
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command", False, {"command": "cat x.md"}, "content", set(), outputs
        )
        assert outputs == []


class TestExecuteSubAgentTaskCatchesEchoLaunderedFabrication:
    """End to end: a synthesis that only 'agrees with itself' via a
    self-authored echo command still gets caught, since that echo no longer
    counts as grounding evidence."""

    def test_self_confirmed_guess_via_echo_gets_swapped(self, ctx, monkeypatch):
        laundered = (
            "I found two mentions of getting old in your vault: a philosophical "
            "note about turning forty, and a personal reflection from last December "
            "about feeling older while everyone around you grows up fast."
        )

        def fake_dispatch(tc, t2c, dirs, profile=None):
            return (
                "call_1",
                "run_command",
                "command=echo ...",
                True,
                laundered,
                {"command": f'echo "{laundered}"'},
            )

        monkeypatch.setattr(
            "sympose.sub_agents.SubAgentEngine._dispatch_tool_call",
            staticmethod(fake_dispatch),
        )

        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content=laundered)
            return _resp(tool_calls=[_fake_tool_call("run_command")])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="what have I written about getting old?", max_tool_turns=4)
        out, _ = SubAgentEngine.execute_sub_agent_task(task)

        assert "isn't actually backed by anything" in out


class TestRegisterRead:
    """What counts as "actually retrieved this run" - not limited to the
    dedicated read_file tool, since a local model reads files via
    `run_command` (`cat`, `sed -n`, `head`...) just as often, live-observed
    in the same run that motivated `_content_unread`."""

    def test_read_file_call_registers_its_path(self):
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "read_file", True, {"path": "Daily/2022-08-29.md"}, "real content", paths, outputs
        )
        assert "Daily/2022-08-29.md" in paths
        assert outputs == ["real content"]
        assert attempted is True

    def test_cat_via_run_command_registers_the_filename(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "real content"),
        )
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "cat /Users/x/garden/Daily/2022-08-29.md"},
            "real content",
            paths,
            outputs,
            {"handle": "t"},
        )
        assert "2022-08-29.md" in {p.rsplit("/", 1)[-1] for p in paths}
        assert outputs == ["real content"]
        assert attempted is True

    def test_find_with_a_glob_registers_nothing(self):
        """No literal filename in the command - it located candidates, it
        didn't retrieve any one file's content. Still counts as an attempt
        (the tool genuinely ran), just not as trusted content."""
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "find /vault/Daily -name '*.md' | shuf -n 1"},
            "",
            paths,
            outputs,
        )
        assert paths == set()
        assert outputs == []
        assert attempted is True

    def test_a_failed_call_registers_nothing_and_is_not_an_attempt(self):
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "read_file", False, {"path": "Daily/2022-08-29.md"}, "", paths, outputs
        )
        assert paths == set()
        assert outputs == []
        assert attempted is False

    def test_vault_sample_registers_the_path_from_its_own_output(self):
        """vault_sample hands back real note content directly - the path
        lives in its own Ground-Truth header, not in args_dict."""
        paths: set[str] = set()
        outputs: list[str] = []
        content = "### Ground-Truth Sandboxed Vault Note (`Daily/2022-08-29.md` - Exact Content):\nbody"
        attempted = SubAgentEngine._register_read(
            "vault_sample", True, {"folder": "Daily"}, content, paths, outputs
        )
        assert "Daily/2022-08-29.md" in paths
        assert outputs == [content]
        assert attempted is True

    def test_vault_search_registers_nothing_in_read_paths_but_counts_as_output(self):
        """Search returns ranked snippets, not full bodies - finding a note
        via search doesn't mean its content was actually retrieved, but the
        snippets are still real externally-sourced evidence."""
        paths: set[str] = set()
        outputs: list[str] = []
        content = "**[1] `Daily/2022-08-29.md`** - ...snippet..."
        attempted = SubAgentEngine._register_read(
            "vault_search", True, {"query": "aliens"}, content, paths, outputs
        )
        assert paths == set()
        assert outputs == [content]
        assert attempted is True

    def test_web_search_counts_as_output_same_as_vault_search(self):
        paths: set[str] = set()
        outputs: list[str] = []
        content = "Result: https://example.com - some real web content"
        attempted = SubAgentEngine._register_read(
            "web_search", True, {"query": "x"}, content, paths, outputs
        )
        assert paths == set()
        assert outputs == [content]
        assert attempted is True

    def test_unrelated_tool_is_not_an_attempt(self):
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "git_status", True, {}, "clean", paths, outputs
        )
        assert outputs == []
        assert attempted is False


class TestRegisterReadEchoLaundering:
    """Round two of the echo-laundering fix (2026-09-17, found by
    /code-review on round one): blocking a *bare* echo wasn't enough - an
    echo whose fabricated text merely *mentions* a real-looking filename
    still matched the filename regex and got trusted. Blocking by the
    command's leading word is structural (what the command does), not a
    phrase list (what it says)."""

    def test_echo_mentioning_a_plausible_filename_is_still_excluded(self):
        paths: set[str] = set()
        outputs: list[str] = []
        attempted = SubAgentEngine._register_read(
            "run_command",
            True,
            {
                "command": (
                    'echo "According to Daily/2026-09-17.md, our favorite '
                    'game is Vault Roulette"'
                )
            },
            "According to Daily/2026-09-17.md, our favorite game is Vault Roulette",
            paths,
            outputs,
        )
        assert paths == set()
        assert outputs == []
        # Still a genuine attempt - the tool call itself succeeded, even
        # though nothing trustworthy came of it - so a confident claim built
        # on top of this must still be judged by _content_unsupported.
        assert attempted is True

    def test_printf_is_excluded_the_same_way(self):
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": 'printf "notes/foo.md says X"'},
            "notes/foo.md says X",
            paths,
            outputs,
        )
        assert paths == set()
        assert outputs == []

    def test_cat_of_a_file_mentioned_alongside_is_not_excluded(self, monkeypatch):
        """The exclusion is specifically about the leading command word, not
        about filenames in general - a genuine read is untouched."""
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "real file content, in full"),
        )
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "cat notes/foo.md"},
            "real file content",
            paths,
            outputs,
            {"handle": "t"},
        )
        assert "notes/foo.md" in paths
        assert outputs == ["real file content"]


class TestGroundedCommandFilesStructuralRedesign:
    """Tier-4: the leading-word blocklist (rounds one-three of the
    echo-laundering fix, above) is a cheap pre-filter now, not the actual
    source of truth - it can only ever catch commands whose *name* looks
    suspicious. `_grounded_command_files` verifies the *output* against a
    real file's actual content instead, closing the whole class of
    "fabricate text via some other command" tricks the blocklist can never
    anticipate one by one."""

    def test_command_not_on_the_blocklist_is_still_rejected_if_output_is_fake(
        self, monkeypatch
    ):
        """python3 -c "print(...)" passes the leading-word check (its
        argv[0] is "python3", not echo/printf/print) - the old, pre-tier-4
        design would have trusted this. The structural check catches it
        anyway, since the printed text doesn't correspond to the real
        file's actual content."""
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(
                lambda profile, name: "the real note says something else entirely"
            ),
        )
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {
                "command": (
                    "python3 -c \"print('According to notes/foo.md, "
                    "the answer is yes')\""
                )
            },
            "According to notes/foo.md, the answer is yes",
            paths,
            outputs,
            {"handle": "t"},
        )
        assert paths == set()
        assert outputs == []

    def test_command_not_on_the_blocklist_is_trusted_when_output_matches_real_content(
        self, monkeypatch
    ):
        """The flip side: a legitimate read via a command with no special
        handling at all (sed) is trusted precisely because its output is
        verifiably a real excerpt - the structural check isn't just
        stricter, it's actually correct in both directions."""
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "line1\nreal excerpt here\nline3"),
        )
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "sed -n '2p' notes/foo.md"},
            "real excerpt here",
            paths,
            outputs,
            {"handle": "t"},
        )
        assert "notes/foo.md" in paths
        assert outputs == ["real excerpt here"]

    def test_no_profile_means_nothing_can_be_verified(self):
        """No profile at all (the default) - there's no sandbox to read a
        real file from, so nothing can be confirmed. Fails closed, not
        open."""
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "cat notes/foo.md"},
            "whatever it printed",
            paths,
            outputs,
        )
        assert paths == set()
        assert outputs == []

    def test_named_file_that_does_not_really_exist_is_not_trusted(self, monkeypatch):
        """A named file that fails to resolve (read_note's own not-found
        message) must never be mistaken for real content the output
        happens to overlap with."""
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: f"Note `{name}` not found in allowed vault folders."),
        )
        paths: set[str] = set()
        outputs: list[str] = []
        SubAgentEngine._register_read(
            "run_command",
            True,
            {"command": "cat ghost.md"},
            "not found in allowed vault folders",
            paths,
            outputs,
            {"handle": "t"},
        )
        assert paths == set()
        assert outputs == []


class TestExecuteSubAgentTaskCatchesUnreadFabrication:
    """End-to-end through execute_sub_agent_task: a completion that names an
    unread note gets overridden before it ever reaches the user."""

    def test_synthesis_naming_an_unread_note_gets_swapped(self, ctx, monkeypatch):
        # ctx's stubbed _dispatch_tool_call always "reads" People/Tin.md -
        # the model's final synthesis instead claims a *different* note.
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(
                    content=(
                        "The note Daily/2024/01-January/2024-01-01.md reads: "
                        "'I climbed a mountain today.'"
                    )
                )
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(get_profile=lambda h: {"handle": h}),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.read_note",
            staticmethod(lambda profile, name: "The real, actually-read content."),
        )

        task = SubAgentTask(task_prompt="find notes on Tin", max_tool_turns=4)
        out, _ = SubAgentEngine.execute_sub_agent_task(task)

        assert "climbed a mountain" not in out
        assert "The real, actually-read content." in out

    def test_synthesis_naming_the_actually_read_note_is_untouched(
        self, ctx, monkeypatch
    ):
        def fake_completion(**kwargs):
            if "tools" not in kwargs:
                return _resp(content="People/Tin.md says Tin is Dylan's mother.")
            return _resp(tool_calls=[_fake_tool_call()])

        monkeypatch.setattr("sympose.sub_agents.litellm.completion", fake_completion)
        task = SubAgentTask(task_prompt="find notes on Tin", max_tool_turns=4)
        out, _ = SubAgentEngine.execute_sub_agent_task(task)
        assert out == "People/Tin.md says Tin is Dylan's mother."


# --------------------------------------------------------------------------- #
#  vault_search / vault_sample - the deterministic vault primitives exposed   #
#  as tools so a vault_read sub-agent gets one structured call instead of     #
#  reconstructing a search or a random pick from find/grep/shuf every time.   #
# --------------------------------------------------------------------------- #


class TestVaultToolSchemasAreOfferedOnlyToVaultReadSkill:
    def test_vault_read_skill_gets_the_tools(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(
                get_profile=lambda h: {"handle": h}, get_persona_memory=lambda p: ""
            ),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_allowed_dirs",
            staticmethod(lambda p: ["/vault"]),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.skill_manager.format_skills_for_prompt",
            lambda skills: "",
        )
        task = SubAgentTask(task_prompt="x", skills=["vault_read"])
        *_, tools, _, _ = SubAgentEngine._build_sub_agent_context(task)
        assert {"vault_search", "vault_sample"} <= {
            t["function"]["name"] for t in tools
        }

    def test_other_skills_dont_get_the_tools(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.ProfileManager",
            lambda: types.SimpleNamespace(
                get_profile=lambda h: {"handle": h}, get_persona_memory=lambda p: ""
            ),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_allowed_dirs",
            staticmethod(lambda p: ["/vault"]),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.skill_manager.format_skills_for_prompt",
            lambda skills: "",
        )
        task = SubAgentTask(task_prompt="x", skills=["web_search"])
        *_, tools, _, _ = SubAgentEngine._build_sub_agent_context(task)
        assert not {"vault_search", "vault_sample"} & {
            t["function"]["name"] for t in tools
        }


class TestRunVaultTool:
    def test_search_formats_results_via_format_search_digest(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.search_structured",
            staticmethod(
                lambda profile, query, target_folder=None, max_results=10: [
                    {"rel_path": "Daily/2022-08-29.md", "snippet": "aliens"}
                ]
            ),
        )
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.format_search_digest",
            staticmethod(lambda query, results: f"DIGEST for {query}: {len(results)} hit(s)"),
        )
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_search", {"query": "aliens"}, {"handle": "samantha"}
        )
        assert ok is True
        assert res == "DIGEST for aliens: 1 hit(s)"

    def test_search_with_no_matches_says_so_without_a_digest_call(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.search_structured",
            staticmethod(lambda *a, **kw: []),
        )
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_search", {"query": "nonexistent"}, {"handle": "samantha"}
        )
        assert ok is True
        assert "No matches" in res

    def test_search_without_a_query_fails_cleanly(self):
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_search", {}, {"handle": "samantha"}
        )
        assert ok is False

    def test_sample_returns_get_random_sample_notes_payload(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_random_sample_notes",
            staticmethod(
                lambda profile, folder, count: f"### Ground-Truth Sandboxed Vault Note (`{folder}/x.md` - Exact Content):\nbody"
            ),
        )
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_sample", {"folder": "Daily"}, {"handle": "samantha"}
        )
        assert ok is True
        assert "Ground-Truth" in res

    def test_sample_with_no_notes_found_fails_cleanly(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.VaultManager.get_random_sample_notes",
            staticmethod(lambda profile, folder, count: ""),
        )
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_sample", {"folder": "Ghost"}, {"handle": "samantha"}
        )
        assert ok is False
        assert "No notes found" in res

    def test_sample_without_a_folder_fails_cleanly(self):
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_sample", {}, {"handle": "samantha"}
        )
        assert ok is False

    def test_no_profile_fails_cleanly_for_either_tool(self):
        ok, res = SubAgentEngine._run_vault_tool("vault_search", {"query": "x"}, None)
        assert ok is False
        ok, res = SubAgentEngine._run_vault_tool("vault_sample", {"folder": "x"}, None)
        assert ok is False

    def test_unknown_tool_name_fails_cleanly(self):
        ok, res = SubAgentEngine._run_vault_tool(
            "vault_teleport", {}, {"handle": "samantha"}
        )
        assert ok is False


class TestDispatchToolCallRoutesVaultTools:
    def test_vault_search_routes_through_run_vault_tool(self, monkeypatch):
        monkeypatch.setattr(
            SubAgentEngine,
            "_run_vault_tool",
            staticmethod(lambda t_name, args, profile: (True, f"ran {t_name} as {profile}")),
        )
        tc = _fake_tool_call_named("vault_search", '{"query": "aliens"}')
        _, t_name, _, ok, res, _ = SubAgentEngine._dispatch_tool_call(
            tc, {}, None, {"handle": "samantha"}
        )
        assert t_name == "vault_search"
        assert ok is True
        assert "ran vault_search" in res


class _FakeSkill:
    def __init__(self, recommended_models=None, minimum_capability_tier=None):
        self.recommended_models = recommended_models or []
        self.minimum_capability_tier = minimum_capability_tier


class TestResolveTargetModelCapabilityTier:
    """ADR-127/128: a skill declaring minimum_capability_tier filters the
    recommended-model pool through model_capability.resolve_capable instead
    of always taking the first recommendation."""

    def test_task_override_always_wins(self, monkeypatch):
        monkeypatch.setattr(
            sub_agents.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(["ignored/model"], "high"),
        )
        task = SubAgentTask(task_prompt="x", skills=["some_skill"], model="explicit/model")
        assert _resolve_target_model(task) == "explicit/model"

    def test_no_skills_recommend_anything_falls_back_to_default(self, monkeypatch):
        monkeypatch.setattr(sub_agents.skill_manager, "get_skill", lambda name: None)
        task = SubAgentTask(task_prompt="x", skills=["unknown_skill"])
        assert _resolve_target_model(task) == sub_agents.DEFAULT_SUB_AGENT_MODEL

    def test_no_capability_tier_declared_takes_first_recommendation_as_before(self, monkeypatch):
        monkeypatch.setattr(
            sub_agents.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(["first/model", "second/model"], None),
        )
        task = SubAgentTask(task_prompt="x", skills=["plain_skill"])
        assert _resolve_target_model(task) == "first/model"

    def test_capability_tier_filters_to_a_model_that_clears_it(self, monkeypatch):
        monkeypatch.setattr(
            sub_agents.skill_manager,
            "get_skill",
            lambda name: _FakeSkill(["weak/model", "capable/model"], "high"),
        )
        monkeypatch.setattr(
            sub_agents.config_manager,
            "get",
            lambda key, default=None: {
                "models.capability_tier_order": ["basic", "standard", "high"],
                "models.capability_tiers": {"capable/model": "high"},
            }.get(key, default),
        )
        task = SubAgentTask(task_prompt="x", skills=["wiki_ingest"])
        assert _resolve_target_model(task) == "capable/model"
