"""
Interactive Terminal UI for Sympose.
"""

import sys
import os
import time
import random
from typing import Optional

try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.markdown import Markdown
except ImportError:
    Console = None
    Markdown = None

from sympose.engine import PersonaEngine
from sympose.ui import TerminalUI
from sympose.completer import SymposeCompleter


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
        return TerminalUI.select_persona(self.console, self.pm.list_personas(), default_handle=default_handle)

    def handle_exit(self, handle: str) -> None:
        """Handles session exit: offers summarization, saves memory/obsidian, and clears terminal."""
        history = self.engine.get_history(handle)
        profile = self.pm.get_profile(handle)
        name = profile.get("name", handle) if profile else handle

        auto_save = bool(self.config.get("session.exit_behavior.auto_save", False))
        default_target = str(self.config.get("session.exit_behavior.default_target", "both")).lower()
        clear_term = bool(self.config.get("session.exit_behavior.clear_terminal", True))

        if history:
            target_to_save = default_target if auto_save else TerminalUI.prompt_exit_choice(self.console, handle, default_target)
            if target_to_save:
                status = None
                if self.console:
                    status = self.console.status(f"[dim italic cyan]{name} is synthesizing session takeaways...[/dim italic cyan]", spinner="dots")
                    status.start()

                try:
                    res = self.engine.summarize_session(handle, target=target_to_save)
                finally:
                    if status:
                        status.stop()

                if self.console and res.get("status") == "success":
                    self.console.print("\n[bold green]✓ Session successfully archived:[/bold green]")
                    for saved in res.get("targets_saved", []):
                        self.console.print(f"  • {saved}")

        self.engine.reset_history(handle)

        if clear_term:
            time.sleep(0.8)
            if self.console:
                self.console.clear()
                self.console.print("[dim cyan]sympose • session ended cleanly[/dim cyan]")
            else:
                os.system("clear")
                print("=== sympose session ended cleanly ===")
        elif self.console:
            self.console.print("[dim cyan]Session ended.[/dim cyan]")

    def run(self, initial_handle: str = "samantha") -> None:
        self.display_banner()
        current_handle = initial_handle

        if current_handle not in self.pm.profiles:
            current_handle = self.select_persona(default_handle="samantha")

        while True:
            profile = self.pm.get_profile(current_handle)
            name = profile.get("name", current_handle) if profile else current_handle
            model = self.engine.model_overrides.get(current_handle, profile.get("model", "")) if profile else ""
            prompt_label = f"\n[bold yellow]You[/bold yellow] (to [bold cyan]@{current_handle}[/bold cyan] | [dim]{model}[/dim])"

            try:
                user_input = Prompt.ask(prompt_label).strip() if self.console else input(f"\nYou (to @{current_handle}): ").strip()
            except (KeyboardInterrupt, EOFError):
                self.handle_exit(current_handle)
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", ":q", "/exit", "/quit"):
                self.handle_exit(current_handle)
                break

            if user_input.startswith("/switch") or (user_input.startswith("@") and len(user_input.split()) == 1):
                self.pm.reload_profiles()
                target = user_input.split()[1].replace("@", "").lower() if user_input.startswith("/switch") and len(user_input.split()) > 1 else user_input.replace("@", "").lower()
                if target.isdigit():
                    plist = self.pm.list_personas()
                    idx = int(target) - 1
                    if 0 <= idx < len(plist):
                        target = plist[idx]["handle"].lower()

                if target in self.pm.profiles:
                    current_handle = target
                    if self.console:
                        self.console.print(f"[bold green]Switched active persona to @{current_handle}[/bold green]")
                else:
                    current_handle = self.select_persona(default_handle=current_handle)
                continue

            if is_command:
                output_chunks = []
                for chunk in self.engine.chat_stream(current_handle, user_input):
                    if chunk == "CLEARED_SESSION":
                        cleared = True
                        if self.console:
                            self.console.clear()
                        else:
                            os.system("clear")
                        self.display_banner()
                        if self.console:
                            self.console.print(f"[bold green]✓ Context cleared for @{current_handle}.[/bold green]")
                        break
                    output_chunks.append(chunk)

                if cleared:
                    continue

                full_cmd_output = "".join(output_chunks).strip()
                if full_cmd_output:
                    if self.console:
                        self.console.print()
                        self.console.print(Markdown(full_cmd_output))
                        self.console.print()
                    else:
                        print(f"\n{full_cmd_output}\n")
                continue

            start_time = time.time()
            status = None

            if self.console:
                phrases = profile.get("thinking_phrases", ["Thinking..."]) if profile else ["Thinking..."]
                chosen_phrase = random.choice(phrases) if phrases else "Thinking..."
                status = self.console.status(f"[dim italic cyan]{name} is {chosen_phrase.lower()}[/dim italic cyan]", spinner="dots")
                status.start()

            first_chunk, first_time, cleared = False, 0.0, False

            try:
                for chunk in self.engine.chat_stream(current_handle, user_input):
                    if chunk == "CLEARED_SESSION":
                        cleared = True
                        if self.console:
                            self.console.clear()
                        else:
                            os.system("clear")
                        self.display_banner()
                        if self.console:
                            self.console.print(f"[bold green]✓ Context cleared for @{current_handle}.[/bold green]")
                        break

                    if not first_chunk:
                        first_chunk = True
                        first_time = time.time() - start_time
                        if status:
                            status.stop()
                            status = None
                        if self.console:
                            self.console.print(f"\n[bold cyan]{name}:[/bold cyan]")
                        else:
                            print(f"\n{name}:")

                    sys.stdout.write(chunk)
                    sys.stdout.flush()
            finally:
                if status:
                    status.stop()

            if cleared:
                continue

            elapsed = time.time() - start_time
            if first_chunk and not is_command:
                short_m = model.split("/")[-1] if "/" in model else model
                badge = f"\n\n[dim cyan][{first_time:.2f}s TTFT | {elapsed:.2f}s total | {short_m}][/dim cyan]\n"
                if self.console:
                    self.console.print(badge)
                else:
                    print(f"\n[{first_time:.2f}s TTFT | {elapsed:.2f}s total | {short_m}]\n")
            else:
                print("\n")
