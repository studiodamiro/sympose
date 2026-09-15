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

from sympose.sub_agents import SubAgentEngine, SubAgentTask


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
            )
        ),
    )
    monkeypatch.setattr(
        SubAgentEngine,
        "_dispatch_tool_call",
        staticmethod(
            lambda tc, t2c, dirs: (
                "call_1",
                "read_file",
                "path=People/Tin.md",
                True,
                "note body: Tin is Dylan's mother.",
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
        call_id, name, arg_summary, ok, res = SubAgentEngine._dispatch_tool_call(
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
        _, name, _, ok, res = SubAgentEngine._dispatch_tool_call(
            _tc("calc_add", '{"a": 1, "b": 41}'), {"calc_add": client}, None
        )
        assert (name, ok, res) == ("calc_add", True, "42")
        assert client.calls == [("calc_add", {"a": 1, "b": 41})]

    def test_unregistered_tool_fails_cleanly(self):
        _, name, _, ok, res = SubAgentEngine._dispatch_tool_call(
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
        call_id, name, arg_summary, ok, res = SubAgentEngine._dispatch_tool_call(
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
        *_, res = SubAgentEngine._dispatch_tool_call(_tc("read_file", "{}"), {}, None)
        assert len(res) < len(huge)
        assert res.endswith("[Output truncated for brevity]...")

    def test_arg_summary_only_includes_whitelisted_keys(self, monkeypatch):
        monkeypatch.setattr(
            "sympose.sub_agents.NativeTools.execute",
            staticmethod(lambda tool_name, args, allowed_dirs=None: (True, "ok")),
        )
        _, _, arg_summary, _, _ = SubAgentEngine._dispatch_tool_call(
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
