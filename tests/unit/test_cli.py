"""
Unit tests for sympose.cli.TerminalInterface.

`run` used to be one function implementing the whole REPL loop inline and
was flagged by mccabe at complexity 52. It was restructured into one method
per phase of a loop iteration (see cli.py's own module docstring), with no
prior test coverage at all for this file — these tests cover the extracted
phases individually plus a few end-to-end `run()` scripts, so a future
change to the loop has a real regression net.
"""

from unittest.mock import MagicMock

import pytest

from sympose.cli import TerminalInterface


def _make_interface(console=None):
    """Builds a TerminalInterface without running __init__ (which would
    touch a real Console/readline setup) — attributes are set directly,
    matching what __init__ would have assigned."""
    ti = TerminalInterface.__new__(TerminalInterface)
    ti.engine = MagicMock()
    ti.pm = ti.engine.pm
    ti.config = ti.engine.config
    ti.console = console
    ti.completer = None
    return ti


@pytest.fixture
def ti():
    return _make_interface(console=None)


class TestResolveActiveModel:
    def test_no_profile_returns_empty(self, ti):
        assert ti._resolve_active_model("samantha", None) == ""

    def test_override_wins_over_profile_default(self, ti):
        ti.engine.model_overrides = {"samantha": "gpt-4o"}
        assert ti._resolve_active_model("samantha", {"model": "claude"}) == "gpt-4o"

    def test_falls_back_to_profile_default(self, ti):
        ti.engine.model_overrides = {}
        assert ti._resolve_active_model("samantha", {"model": "claude"}) == "claude"


class TestReadUserInput:
    def test_eof_reports_hit_eof(self, ti, monkeypatch):
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))
        text, hit_eof = ti._read_user_input("samantha", "gpt-4o")
        assert text is None and hit_eof is True

    def test_keyboard_interrupt_is_not_eof(self, ti, monkeypatch):
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=KeyboardInterrupt))
        text, hit_eof = ti._read_user_input("samantha", "gpt-4o")
        assert text is None and hit_eof is False

    def test_normal_input_is_stripped(self, ti, monkeypatch):
        monkeypatch.setattr("builtins.input", MagicMock(return_value="  hello  "))
        text, hit_eof = ti._read_user_input("samantha", "gpt-4o")
        assert text == "hello" and hit_eof is False


class TestMaybeSwitchPersona:
    def test_non_switch_input_returns_none(self, ti):
        assert ti._maybe_switch_persona("hello there", "samantha") is None

    def test_switch_to_known_handle(self, ti):
        ti.pm.profiles = {"samantha": {}, "rosalind": {}}
        result = ti._maybe_switch_persona("/switch rosalind", "samantha")
        assert result == "rosalind"

    def test_bare_mention_switches(self, ti):
        ti.pm.profiles = {"samantha": {}, "rosalind": {}}
        result = ti._maybe_switch_persona("@rosalind", "samantha")
        assert result == "rosalind"

    def test_switch_by_index(self, ti):
        ti.pm.profiles = {"samantha": {}, "rosalind": {}}
        ti.pm.list_personas.return_value = [
            {"handle": "samantha"},
            {"handle": "rosalind"},
        ]
        result = ti._maybe_switch_persona("/switch 2", "samantha")
        assert result == "rosalind"

    def test_unknown_target_falls_back_to_selector(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        monkeypatch.setattr(ti, "select_persona", lambda default_handle: "samantha")
        result = ti._maybe_switch_persona("/switch ghost", "samantha")
        assert result == "samantha"

    def test_bare_switch_with_no_target_falls_back_to_selector(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        monkeypatch.setattr(ti, "select_persona", lambda default_handle: "samantha")
        result = ti._maybe_switch_persona("/switch", "samantha")
        assert result == "samantha"


class TestRenderChunk:
    def test_buffered_mode_accumulates(self, ti):
        buf = []
        ti._render_chunk("hello", "buffered", buf)
        assert buf == ["hello"]

    def test_raw_mode_writes_immediately(self, ti, capsys):
        ti._render_chunk("hello", "raw", [])
        assert capsys.readouterr().out == "hello"

    def test_hybrid_plain_text_writes_immediately(self, ti, capsys):
        ti._render_chunk("plain text", "hybrid", [])
        assert capsys.readouterr().out == "plain text"

    def test_hybrid_blockquote_without_console_writes_raw(self, ti, capsys):
        ti._render_chunk("> a quoted line", "hybrid", [])
        assert capsys.readouterr().out == "> a quoted line"

    def test_hybrid_blockquote_with_console_renders_markdown(self, monkeypatch):
        console = MagicMock()
        ti = _make_interface(console=console)
        monkeypatch.setattr(
            "sympose.cli.TerminalUI.render_markdown", MagicMock()
        )
        ti._render_chunk("\n\n> quoted", "hybrid", [])
        console.print.assert_called_once_with()


class TestPrintTimingBadge:
    def test_no_first_chunk_prints_nothing(self, ti, capsys):
        ti._print_timing_badge(0.0, False, 0.0, "gpt-4o")
        assert capsys.readouterr().out == ""

    def test_first_chunk_prints_badge(self, ti, capsys):
        ti._print_timing_badge(0.0, True, 0.5, "openrouter/anthropic/claude-3.5")
        out = capsys.readouterr().out
        assert "claude-3.5" in out and "TTFT" in out


class TestStopStatusHelpers:
    def test_stop_status_stops_and_clears(self, ti):
        status = MagicMock()
        state = {"status": status}
        ti._stop_status(state)
        status.stop.assert_called_once()
        assert state["status"] is None

    def test_stop_status_noop_when_absent(self, ti):
        state = {"status": None}
        ti._stop_status(state)  # must not raise
        assert state["status"] is None

    def test_stop_sub_status_stops_and_clears(self, ti):
        sub = MagicMock()
        state = {"sub_status": sub}
        ti._stop_sub_status(state)
        sub.stop.assert_called_once()
        assert state["sub_status"] is None


class TestSubAgentProgressHook:
    def test_no_console_is_a_noop(self, ti):
        state = {"status": None, "sub_status": None}
        hook = ti._make_sub_agent_progress_hook("Samantha", state)
        hook("searching vault")
        assert state["sub_status"] is None

    def test_first_call_creates_status_and_stops_thinking_spinner(self):
        console = MagicMock()
        ti = _make_interface(console=console)
        thinking_status = MagicMock()
        state = {"status": thinking_status, "sub_status": None}
        hook = ti._make_sub_agent_progress_hook("Samantha", state)
        hook("running vault_read")
        thinking_status.stop.assert_called_once()
        assert state["status"] is None
        console.status.assert_called_once()
        state["sub_status"].start.assert_called_once()

    def test_second_call_updates_existing_status(self):
        console = MagicMock()
        ti = _make_interface(console=console)
        state = {"status": None, "sub_status": MagicMock()}
        hook = ti._make_sub_agent_progress_hook("Samantha", state)
        hook("second call")
        state["sub_status"].update.assert_called_once()

    def test_long_summary_is_truncated(self):
        console = MagicMock()
        ti = _make_interface(console=console)
        state = {"status": None, "sub_status": None}
        hook = ti._make_sub_agent_progress_hook("Samantha", state)
        hook("x" * 200)
        text_arg = console.status.call_args[0][0]
        assert "..." in text_arg


class TestRunCommandTurn:
    def test_normal_output_is_rendered(self, ti, monkeypatch):
        ti.engine.chat_stream.return_value = iter(["hello ", "world"])
        rendered = MagicMock()
        monkeypatch.setattr("sympose.cli.TerminalUI.render_markdown", rendered)
        ti._run_command_turn("samantha", "/help")
        rendered.assert_called_once_with(None, "hello world")

    def test_cleared_session_clears_screen(self, ti, monkeypatch):
        ti.engine.chat_stream.return_value = iter(["CLEARED_SESSION"])
        monkeypatch.setattr(ti, "display_banner", MagicMock())
        ti._run_command_turn("samantha", "/clear")
        ti.display_banner.assert_called_once()

    def test_keyboard_interrupt_is_swallowed(self, ti, capsys):
        def _raise(*a, **kw):
            raise KeyboardInterrupt

        ti.engine.chat_stream.side_effect = _raise
        ti._run_command_turn("samantha", "/save")  # must not raise
        assert "Command cancelled" in capsys.readouterr().out


class TestStreamChatReply:
    def test_basic_stream_reports_first_chunk_and_time(self, ti, monkeypatch):
        ti.engine.chat_stream.return_value = iter(["Hello", " world"])
        ti.engine.config.get.return_value = "raw"
        state = {"status": None, "sub_status": None}
        cleared, first_chunk, first_time = ti._stream_chat_reply(
            "samantha", "hi", "Samantha", lambda s: None, state, 0.0
        )
        assert cleared is False
        assert first_chunk is True
        assert first_time >= 0.0

    def test_cleared_session_stops_early(self, ti, monkeypatch):
        ti.engine.chat_stream.return_value = iter(["CLEARED_SESSION", "unreachable"])
        ti.engine.config.get.return_value = "raw"
        monkeypatch.setattr(ti, "display_banner", MagicMock())
        state = {"status": None, "sub_status": None}
        cleared, first_chunk, _ = ti._stream_chat_reply(
            "samantha", "hi", "Samantha", lambda s: None, state, 0.0
        )
        assert cleared is True
        assert first_chunk is False


class TestRunEndToEnd:
    """Drives `run()` to completion with a scripted `_read_user_input` and
    a mocked `chat_stream`, since the loop itself is otherwise infinite."""

    def _scripted(self, ti, inputs, monkeypatch):
        monkeypatch.setattr(ti, "_read_user_input", MagicMock(side_effect=inputs))

    def test_eof_exits_via_handle_exit(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        ti.pm.get_profile.return_value = {"name": "Samantha"}
        self._scripted(ti, [(None, True)], monkeypatch)
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        ti.run(initial_handle="samantha")
        ti.handle_exit.assert_called_once_with("samantha")

    def test_exit_keyword_exits(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        ti.pm.get_profile.return_value = {"name": "Samantha"}
        self._scripted(ti, [("exit", False)], monkeypatch)
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        ti.run(initial_handle="samantha")
        ti.handle_exit.assert_called_once_with("samantha")

    def test_empty_input_loops_then_exits(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        ti.pm.get_profile.return_value = {"name": "Samantha"}
        self._scripted(ti, [("", False), ("/exit", False)], monkeypatch)
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        ti.run(initial_handle="samantha")
        ti.handle_exit.assert_called_once_with("samantha")

    def test_slash_command_routes_to_command_turn_then_exits(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        ti.pm.get_profile.return_value = {"name": "Samantha"}
        self._scripted(ti, [("/help", False), ("/exit", False)], monkeypatch)
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        monkeypatch.setattr(ti, "_run_command_turn", MagicMock())
        ti.run(initial_handle="samantha")
        ti._run_command_turn.assert_called_once_with("samantha", "/help")

    def test_normal_message_routes_to_chat_turn_then_exits(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}}
        ti.pm.get_profile.return_value = {"name": "Samantha", "model": "gpt-4o"}
        ti.engine.model_overrides = {}
        self._scripted(
            ti, [("hello there", False), ("/exit", False)], monkeypatch
        )
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        monkeypatch.setattr(ti, "_run_chat_turn", MagicMock())
        ti.run(initial_handle="samantha")
        ti._run_chat_turn.assert_called_once_with(
            "samantha", "hello there", {"name": "Samantha", "model": "gpt-4o"},
            "Samantha", "gpt-4o",
        )

    def test_switch_command_changes_handle(self, ti, monkeypatch):
        ti.pm.profiles = {"samantha": {}, "rosalind": {}}
        ti.pm.get_profile.side_effect = lambda h: {"name": h.capitalize()}
        self._scripted(
            ti, [("/switch rosalind", False), ("/exit", False)], monkeypatch
        )
        monkeypatch.setattr(ti, "handle_exit", MagicMock())
        ti.run(initial_handle="samantha")
        ti.handle_exit.assert_called_once_with("rosalind")
