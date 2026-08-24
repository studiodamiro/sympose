"""
Interactive Terminal UI for Sympose.
"""

import sys
import time
import random
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None

from sympose.engine import PersonaEngine


class TerminalInterface:
    """Rich interactive Terminal UI for Sympose with smooth real-time streaming."""

    THINKING_PHRASES = {
        "samantha": [
            "Connecting high-level dots...",
            "Synthesizing strategic options...",
            "Consulting the symposium...",
            "Distilling signal from noise...",
            "Formulating the master blueprint...",
            "Aligning architecture and goals...",
        ],
        "grace": [
            "Decompiling assumptions...",
            "Eliminating unnecessary abstractions...",
            "Refactoring the logic paths...",
            "Inspecting compiler circuits...",
            "Hunting for zero-bloat solutions...",
            "Verifying system constraints...",
        ],
        "aurelius": [
            "Reflecting stoically...",
            "Examining what is within our control...",
            "Weighing the inner citadel...",
            "Contemplating the nature of things...",
            "Distilling clarity from chaos...",
            "Cultivating steady wisdom...",
        ],
    }

    def __init__(self, engine: PersonaEngine):
        self.engine = engine
        self.pm = engine.pm
        self.console = Console() if Console else None

    def display_banner(self) -> None:
        if not self.console:
            print("=== sympose // multi-model agent hub ===")
            return

        banner_text = Text()
        banner_text.append("sympose // multi-model agent hub\n", style="bold cyan")
        banner_text.append("minimalist runtime for macos & slack\n", style="dim white")
        banner_text.append("commands: /help  |  switch: /switch  |  exit: quit", style="dim cyan")

        self.console.print(Panel(banner_text, border_style="dim cyan", padding=(1, 2)))

    def select_persona(self, default_handle: str = "samantha") -> str:
        profiles = self.pm.list_personas()
        if not profiles:
            if self.console:
                self.console.print("[bold red]No profiles found in profiles/ directory.[/bold red]")
            return default_handle

        if not self.console:
            return default_handle

        table = Table(title="Personas", border_style="dim cyan", show_header=True)
        table.add_column("Handle", style="bold yellow")
        table.add_column("Name", style="bold white")
        table.add_column("Role / Title", style="cyan")
        table.add_column("Default Model", style="green")
        table.add_column("Sandbox", style="magenta")

        for p in profiles:
            table.add_row(
                f"@{p.get('handle')}",
                p.get("name", ""),
                p.get("title", ""),
                p.get("model", ""),
                f"{p.get('vault_folder', 'none')}/"
            )

        self.console.print(table)
        valid_handles = [p["handle"].lower() for p in profiles]
        raw_choice = Prompt.ask(
            "\nSelect persona handle",
            default=default_handle,
            choices=valid_handles,
            case_sensitive=False
        )
        return raw_choice.lower().replace("@", "").strip()

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
                if self.console:
                    user_input = Prompt.ask(prompt_label).strip()
                else:
                    user_input = input(f"\nYou (to @{current_handle}): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting sympose.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", ":q"):
                if self.console:
                    self.console.print("[dim cyan]Session ended.[/dim cyan]")
                break

            if user_input.startswith("/switch"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].replace("@", "") in self.pm.profiles:
                    current_handle = parts[1].replace("@", "").lower()
                    if self.console:
                        self.console.print(f"[bold green]Switched to @{current_handle}[/bold green]")
                else:
                    current_handle = self.select_persona(default_handle=current_handle)
                continue

            is_command = user_input.startswith("/")
            start_time = time.time()

            # For regular prompts, show active thinking spinner until first token streams
            status = None
            if self.console and not is_command:
                phrases = self.THINKING_PHRASES.get(current_handle.lower(), ["Thinking..."])
                witty_phrase = random.choice(phrases)
                status = self.console.status(f"[dim italic cyan]{name} is {witty_phrase.lower()}[/dim italic cyan]", spinner="dots")
                status.start()

            first_chunk_received = False

            try:
                for chunk in self.engine.chat_stream(current_handle, user_input):
                    if not first_chunk_received:
                        first_chunk_received = True
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

            total_elapsed = time.time() - start_time

            # Print clean telemetry badge
            if first_chunk_received and not is_command:
                short_model = model.split("/")[-1] if "/" in model else model
                telemetry_badge = f"\n\n[dim cyan][{total_elapsed:.2f}s | {short_model}][/dim cyan]\n"
                if self.console:
                    self.console.print(telemetry_badge)
                else:
                    print(f"\n[{total_elapsed:.2f}s | {short_model}]\n")
            else:
                print("\n")
