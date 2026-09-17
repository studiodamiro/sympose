"""
Interactive Terminal UI for Sympose.

`TerminalInterface.run` used to be one function implementing the whole
REPL loop inline — reading input, exit handling, persona switching,
slash-command dispatch, and the streaming-reply renderer (with its own
nested closures for the sub-agent progress spinner) — and mccabe flagged
it at complexity 52. Restructured the same way as the other worst
complexity offenders this pass (`commands.py`'s `intercept`, `actions.py`'s
`execute_actions`): each phase of one loop iteration is now its own
`TerminalInterface` method, so `run` itself is just the loop skeleton
calling into them. Unlike those two, this class already has `self` to
carry shared state (`self.console`, `self.engine`, `self.pm`,
`self.config`), so no separate context object was needed — the one place
that still needed a shared mutable box across a closure (the "thinking"
spinner and the sub-agent-progress spinner, which can each stop the
other) uses a small `state` dict instead of the original's `nonlocal`.
"""

import os
import sys
import time
from collections.abc import Callable
from typing import Any

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.prompt import Prompt
except ImportError:
    Console = None
    Markdown = None

from sympose.completer import SymposeCompleter
from sympose.engine import PersonaEngine
from sympose.ui import AnimatedStatus, TerminalUI


class TerminalInterface:
    """Rich interactive Terminal UI for Sympose with smooth real-time streaming."""

    def __init__(self, engine: PersonaEngine):
        self.engine = engine
        self.pm = engine.pm
        self.config = engine.config
        self.console = TerminalUI.get_console()
        self.completer = SymposeCompleter.setup_readline(self.engine)

    def display_banner(self) -> None:
        TerminalUI.display_banner(self.console)

    def select_persona(self, default_handle: str = "samantha") -> str:
        self.pm.reload_profiles()
        return TerminalUI.select_persona(
            self.console, self.pm.list_personas(), default_handle=default_handle
        )

    def handle_exit(self, handle: str) -> None:
        """Handles session exit: offers summarization, saves memory/obsidian, and clears terminal."""
        history = self.engine.get_history(handle)
        profile = self.pm.get_profile(handle)
        name = profile.get("name", handle) if profile else handle

        auto_save = bool(self.config.get("session.exit_behavior.auto_save"))
        default_target = str(
            self.config.get("session.exit_behavior.default_target")
        ).lower()
        clear_term = bool(self.config.get("session.exit_behavior.clear_terminal"))

        if history:
            target_to_save = (
                default_target
                if auto_save
                else TerminalUI.prompt_exit_choice(self.console, handle, default_target)
            )
            if target_to_save:
                status = None
                if self.console:
                    status = self.console.status(
                        f"[dim italic cyan]{name} is synthesizing session takeaways...[/dim italic cyan]",
                        spinner="dots",
                    )
                    status.start()

                try:
                    res = self.engine.summarize_session(handle, target=target_to_save)
                finally:
                    if status:
                        status.stop()

                if self.console and res.get("status") == "success":
                    self.console.print(
                        "\n[bold green]✓ Session successfully archived:[/bold green]"
                    )
                    for saved in res.get("targets_saved", []):
                        self.console.print(f"  • {saved}")

        self.engine.reset_history(handle)

        if clear_term:
            time.sleep(0.8)
            if self.console:
                self.console.clear()
                self.console.print(
                    "[dim cyan]sympose • session ended cleanly[/dim cyan]"
                )
            else:
                os.system("clear")
                print("=== sympose session ended cleanly ===")
        elif self.console:
            self.console.print("[dim cyan]Session ended.[/dim cyan]")

    # --- One loop iteration's phases, in the order `run` calls them --------
    def _resolve_active_model(self, current_handle: str, profile: dict | None) -> str:
        return (
            self.engine.model_overrides.get(current_handle, profile.get("model", ""))
            if profile
            else ""
        )

    def _read_user_input(self, current_handle: str, model: str) -> tuple[str | None, bool]:
        """Reads one line of user input. Returns (text, hit_eof) — hit_eof
        is True on Ctrl+D; text is None on Ctrl+C (nothing to process, but
        not an exit either)."""
        prompt_label = (
            f"\n[bold yellow]You[/bold yellow] (to [bold cyan]@{current_handle}[/bold cyan] | [dim]{model}[/dim])"
        )
        try:
            text = (
                Prompt.ask(prompt_label).strip()
                if self.console
                else input(f"\nYou (to @{current_handle}): ").strip()
            )
            return text, False
        except EOFError:
            return None, True
        except KeyboardInterrupt:
            if self.console:
                self.console.print("\n[dim](Type /exit or press Ctrl+D to quit)[/dim]")
            else:
                print("\n(Type /exit or press Ctrl+D to quit)")
            return None, False

    def _maybe_switch_persona(self, user_input: str, current_handle: str) -> str | None:
        """Handles `/switch [target]` and a bare `@handle` mention as a
        persona switch. Returns the new current_handle, or None when
        `user_input` wasn't a switch command at all."""
        is_switch_cmd = user_input.startswith("/switch")
        is_bare_mention = user_input.startswith("@") and len(user_input.split()) == 1
        if not (is_switch_cmd or is_bare_mention):
            return None

        self.pm.reload_profiles()
        target = (
            user_input.split()[1].replace("@", "").lower()
            if is_switch_cmd and len(user_input.split()) > 1
            else user_input.replace("@", "").lower()
        )
        if target.isdigit():
            plist = self.pm.list_personas()
            idx = int(target) - 1
            if 0 <= idx < len(plist):
                target = plist[idx]["handle"].lower()

        if target in self.pm.profiles:
            if self.console:
                self.console.print(
                    f"\n[bold green]✓ Switched active persona to @{target}[/bold green]"
                )
            return target

        new_handle = self.select_persona(default_handle=current_handle)
        if self.console:
            self.console.print(
                f"\n[bold green]✓ Active persona: @{new_handle}[/bold green]"
            )
        return new_handle

    def _clear_screen_and_banner(self, current_handle: str) -> None:
        if self.console:
            self.console.clear()
        else:
            os.system("clear")
        self.display_banner()
        if self.console:
            self.console.print(
                f"\n[bold green]✓ Context cleared for @{current_handle}.[/bold green]"
            )

    def _run_command_turn(self, current_handle: str, user_input: str) -> None:
        """Runs a slash command through the engine and renders its
        (non-streaming, no thinking-spinner) output."""
        output_chunks = []
        cleared = False
        try:
            for chunk in self.engine.chat_stream(current_handle, user_input):
                if chunk == "CLEARED_SESSION":
                    cleared = True
                    self._clear_screen_and_banner(current_handle)
                    break
                output_chunks.append(chunk)
        except KeyboardInterrupt:
            if self.console:
                self.console.print(
                    "\n\n[dim yellow]^C [Command cancelled][/dim yellow]"
                )
            else:
                print("\n\n^C [Command cancelled]")
            return

        if cleared:
            return

        full_cmd_output = "".join(output_chunks).strip()
        if full_cmd_output:
            TerminalUI.render_markdown(self.console, full_cmd_output)

    def _stop_status(self, state: dict[str, Any]) -> None:
        if state.get("status"):
            state["status"].stop()
            state["status"] = None

    def _stop_sub_status(self, state: dict[str, Any]) -> None:
        if state.get("sub_status") is not None:
            state["sub_status"].stop()
            state["sub_status"] = None

    def _make_sub_agent_progress_hook(
        self, name: str, state: dict[str, Any]
    ) -> Callable[[str], None]:
        """Live sub-agent tool-call status: fills what would otherwise be a
        silent multi-second wait (a sub-agent's whole tool loop runs
        synchronously before anything is yielded) with the actual command
        it's running right now, instead of leaving the generic "thinking"
        spinner up. Lazily created on the first callback so a turn with no
        sub-agent never touches it."""

        def _on_sub_agent_progress(call_summary: str) -> None:
            if not self.console:
                return
            shown = (
                call_summary if len(call_summary) <= 88 else call_summary[:85] + "..."
            )
            text = f"[dim italic cyan]{name} is running: {shown}[/dim italic cyan]"
            if state.get("sub_status") is None:
                # A sub-agent can spawn before any visible text has streamed
                # yet (e.g. the model's very first move is the spawn tag) —
                # the canned "thinking" spinner would still be live in that
                # case, and Rich only allows one live display per console.
                self._stop_status(state)
                state["sub_status"] = self.console.status(text, spinner="dots")
                state["sub_status"].start()
            else:
                state["sub_status"].update(text)

        return _on_sub_agent_progress

    def _render_chunk(
        self, chunk: str, render_mode: str, buffered_chunks: list[str]
    ) -> None:
        if render_mode == "buffered":
            buffered_chunks.append(chunk)
            return
        if render_mode == "raw":
            sys.stdout.write(chunk)
            sys.stdout.flush()
            return
        # "hybrid" default
        is_blockquote = (
            chunk.startswith("\n\n>") or "\n> " in chunk or chunk.startswith("> ")
        )
        if is_blockquote and self.console:
            self.console.print()
            TerminalUI.render_markdown(self.console, chunk.strip())
        else:
            sys.stdout.write(chunk)
            sys.stdout.flush()

    def _print_timing_badge(
        self, start_time: float, first_chunk: bool, first_time: float, model: str
    ) -> None:
        if not first_chunk:
            return
        elapsed = time.time() - start_time
        short_m = model.split("/")[-1] if "/" in model else model
        badge = f"\n\n[dim cyan][{first_time:.2f}s TTFT | {elapsed:.2f}s total | {short_m}][/dim cyan]"
        if self.console:
            self.console.print(badge)
        else:
            print(f"\n[{first_time:.2f}s TTFT | {elapsed:.2f}s total | {short_m}]")

    def _print_reply_header(self, name: str) -> None:
        if self.console:
            self.console.print(f"\n[bold cyan]{name}:[/bold cyan]")
        else:
            print(f"\n{name}:")

    def _handle_first_chunk(
        self, name: str, render_mode: str, state: dict[str, Any]
    ) -> None:
        if render_mode == "buffered":
            return
        self._stop_status(state)
        self._print_reply_header(name)

    def _flush_buffered_reply(
        self, name: str, buffered_chunks: list[str], state: dict[str, Any]
    ) -> None:
        self._stop_status(state)
        if self.console:
            self._print_reply_header(name)
            TerminalUI.render_markdown_typewriter(
                self.console, "".join(buffered_chunks).strip()
            )
        else:
            self._print_reply_header(name)
            print("".join(buffered_chunks).strip())

    def _stream_chat_reply(
        self,
        current_handle: str,
        user_input: str,
        name: str,
        on_progress: Callable[[str], None],
        state: dict[str, Any],
        start_time: float,
    ) -> tuple[bool, bool, float]:
        """Consumes the engine's stream for one chat turn, rendering each
        chunk as it arrives. Returns (cleared, first_chunk, first_time)."""
        first_chunk, first_time, cleared = False, 0.0, False
        render_mode = str(self.engine.config.get("performance.render_mode")).lower().strip()
        buffered_chunks: list[str] = []

        for chunk in self.engine.chat_stream(
            current_handle, user_input, on_sub_agent_progress=on_progress
        ):
            if chunk == "CLEARED_SESSION":
                cleared = True
                self._clear_screen_and_banner(current_handle)
                break

            # Any real content chunk means the sub-agent (if one ran) is
            # done — its final report is what's about to print.
            self._stop_sub_status(state)

            if not first_chunk:
                first_chunk = True
                first_time = time.time() - start_time
                self._handle_first_chunk(name, render_mode, state)

            self._render_chunk(chunk, render_mode, buffered_chunks)

        if render_mode == "buffered" and buffered_chunks and not cleared:
            self._flush_buffered_reply(name, buffered_chunks, state)

        return cleared, first_chunk, first_time

    def _run_chat_turn(
        self,
        current_handle: str,
        user_input: str,
        profile: dict | None,
        name: str,
        model: str,
    ) -> None:
        """Streams a normal (non-command) chat turn: a "thinking" spinner
        until the first chunk arrives, live sub-agent progress in place of
        it if one spawns, then the reply itself rendered per
        `performance.render_mode`, and a closing TTFT/total-time badge."""
        start_time = time.time()
        state: dict[str, Any] = {"status": None, "sub_status": None}

        if self.console:
            phrases = (
                profile.get("thinking_phrases", ["Thinking..."])
                if profile
                else ["Thinking..."]
            )
            state["status"] = AnimatedStatus(self.console, name, phrases).start()

        on_progress = self._make_sub_agent_progress_hook(name, state)

        try:
            cleared, first_chunk, first_time = self._stream_chat_reply(
                current_handle, user_input, name, on_progress, state, start_time
            )
        except KeyboardInterrupt:
            self._stop_status(state)
            self._stop_sub_status(state)
            if self.console:
                self.console.print(
                    f"\n\n[dim yellow]^C [Interrupted @{current_handle}][/dim yellow]"
                )
            else:
                print(f"\n\n^C [Interrupted @{current_handle}]")
            return
        finally:
            self._stop_status(state)
            self._stop_sub_status(state)

        if cleared:
            return

        self._print_timing_badge(start_time, first_chunk, first_time, model)

    def run(self, initial_handle: str = "samantha") -> None:
        self.display_banner()
        current_handle = initial_handle

        if current_handle not in self.pm.profiles:
            current_handle = self.select_persona(default_handle="samantha")

        while True:
            profile = self.pm.get_profile(current_handle)
            name = profile.get("name", current_handle) if profile else current_handle
            model = self._resolve_active_model(current_handle, profile)

            user_input, hit_eof = self._read_user_input(current_handle, model)
            if hit_eof:
                self.handle_exit(current_handle)
                break
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", ":q", "/exit", "/quit"):
                self.handle_exit(current_handle)
                break

            switched = self._maybe_switch_persona(user_input, current_handle)
            if switched is not None:
                current_handle = switched
                continue

            if user_input.startswith("/"):
                self._run_command_turn(current_handle, user_input)
                continue

            self._run_chat_turn(current_handle, user_input, profile, name, model)
