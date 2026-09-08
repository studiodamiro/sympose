"""
Unit tests for sympose.workers.WorkerEngine — the tool-loop budget backstop.

Regression: a worker that read the relevant notes but then spent its remaining
tool turns on redundant greps hit `max_worker_tool_turns` and returned
"reached maximum tool turns without completing final synthesis" — throwing away
the content it had already gathered. The final turn now disables tools and
forces a synthesis; if that still comes back empty, `_forced_synthesis` is the
backstop.
"""

import types

import pytest

from sympose.workers import WorkerEngine, WorkerTask


class _FakeChoice:
    def __init__(self, content=None, tool_calls=None):
        self.message = types.SimpleNamespace(
            content=content, tool_calls=tool_calls,
            to_dict=lambda: {"role": "assistant", "content": content or ""},
        )


def _resp(content=None, tool_calls=None):
    return types.SimpleNamespace(choices=[_FakeChoice(content, tool_calls)])


def _fake_tool_call(name="read_file"):
    return types.SimpleNamespace(
        id="call_1",
        function=types.SimpleNamespace(name=name, arguments='{"path": "People/Tin.md"}'),
    )


@pytest.fixture
def ctx(monkeypatch):
    """Stub _build_worker_context so no real MCP / model setup runs."""
    monkeypatch.setattr(
        WorkerEngine, "_build_worker_context",
        classmethod(lambda cls, task: (
            "sys", "gemini/gemini-3.6-flash", [{"role": "user", "content": task.task_prompt}],
            {}, {}, [{"type": "function", "function": {"name": "read_file"}}], ["/vault"],
        )),
    )
    monkeypatch.setattr(WorkerEngine, "_dispatch_tool_call",
                        staticmethod(lambda tc, t2c, dirs: ("call_1", "read_file", "path=People/Tin.md", True, "note body: Tin is Dylan's mother.")))
    monkeypatch.setattr(WorkerEngine, "_inject_api_key", staticmethod(lambda kw, m: None))


def test_budget_exhaustion_forces_synthesis_instead_of_failure(ctx, monkeypatch):
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        # No tools passed on the final turn -> that's the forced-synthesis call.
        if "tools" not in kwargs:
            return _resp(content="Tin is Dylan's mother; you noted you miss her.")
        return _resp(tool_calls=[_fake_tool_call()])

    monkeypatch.setattr("sympose.workers.litellm.completion", fake_completion)

    task = WorkerTask(task_prompt="find notes on Tin and Dylan", max_tool_turns=4)
    out, tool_calls = WorkerEngine.execute_worker_task(task)

    assert "Tin is Dylan's mother" in out
    assert "maximum tool turns" not in out
    assert len(tool_calls) == 3  # turns 1-3 tool-called; turn 4 was tools-off synthesis


def test_normal_completion_unaffected(ctx, monkeypatch):
    def fake_completion(**kwargs):
        return _resp(content="done: the answer")

    monkeypatch.setattr("sympose.workers.litellm.completion", fake_completion)
    out, _ = WorkerEngine.execute_worker_task(WorkerTask(task_prompt="x", max_tool_turns=8))
    assert out == "done: the answer"


def test_forced_synthesis_empty_falls_back_to_notice(ctx, monkeypatch):
    def fake_completion(**kwargs):
        if "tools" not in kwargs:
            return _resp(content="")  # forced synth yields nothing
        return _resp(tool_calls=[_fake_tool_call()])

    monkeypatch.setattr("sympose.workers.litellm.completion", fake_completion)
    out, _ = WorkerEngine.execute_worker_task(WorkerTask(task_prompt="x", max_tool_turns=3))
    assert "tool budget" in out
