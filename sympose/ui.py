"""
Terminal UI Presentation, Banners & Modals for Sympose.
"""

from typing import Optional, List, Dict, Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None


class TerminalUI:
    """Provides styled Rich UI panels, tables, and modal dialogs."""

    @staticmethod
    def display_banner(console: Optional[Any]) -> None:
        if not console:
            print("=== sympose // multi-model agent hub ===")
            return

        banner = Text()
        banner.append("sympose // multi-model agent hub\n", style="bold cyan")
        banner.append("minimalist runtime for macos & slack\n", style="dim white")
        banner.append("commands: /help | /save | /config | switch: /switch | exit: /exit", style="dim cyan")
        console.print(Panel(banner, border_style="dim cyan", padding=(1, 2)))

    @staticmethod
    def select_persona(console: Optional[Any], profiles: List[Dict[str, Any]], default_handle: str = "samantha") -> str:
        if not profiles or not console:
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

        console.print(table)
        valid = [p["handle"].lower() for p in profiles]
        choice = Prompt.ask("\nSelect persona handle", default=default_handle, choices=valid, case_sensitive=False)
        return choice.lower().replace("@", "").strip()

    @staticmethod
    def prompt_exit_choice(console: Optional[Any], handle: str, default_target: str = "both") -> Optional[str]:
        """Displays exit modal dialog for memory/obsidian persistence."""
        if not console:
            return default_target if default_target in ("memory", "obsidian", "both") else None

        console.print(f"\n[bold yellow]Active session with @{handle} detected.[/bold yellow]")
        menu_text = (
            "[bold cyan][1][/bold cyan] Memory Only (Append to persistent `_memory.md`)\n"
            "[bold cyan][2][/bold cyan] Obsidian Only (Save structured note to vault)\n"
            "[bold cyan][3][/bold cyan] Both (Memory + Obsidian) [Default]\n"
            "[bold cyan][4][/bold cyan] Discard & Exit (No save)"
        )
        console.print(Panel(menu_text, title="Save Session Takeaways?", border_style="dim cyan"))

        def_opt = "1" if default_target == "memory" else ("2" if default_target == "obsidian" else ("4" if default_target == "discard" else "3"))
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default=def_opt)

        mapping = {"1": "memory", "2": "obsidian", "3": "both", "4": None}
        return mapping.get(choice)
