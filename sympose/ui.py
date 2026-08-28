"""
Terminal UI Presentation, Design System & Modals for Sympose.
"""

import os
from typing import Optional, List, Dict, Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
    from rich.box import ROUNDED
    from rich.theme import Theme
    from rich.markdown import Markdown, Heading
    if Heading and hasattr(Heading, "LEVEL_ALIGN"):
        Heading.LEVEL_ALIGN["h1"] = "left"
except ImportError:
    Console = None
    ROUNDED = None
    Markdown = None
    Heading = None

SYMPOSE_THEME = Theme({
    "sympose.brand": "bold cyan",
    "sympose.user": "bold yellow",
    "sympose.agent": "bold cyan",
    "sympose.model": "bold green",
    "sympose.path": "magenta",
    "sympose.dim": "dim white",
    "sympose.success": "bold green",
    "sympose.error": "bold red",
    "sympose.warning": "bold yellow",
    "sympose.border": "dim cyan",
    "markdown.h1": "bold cyan",
    "markdown.h2": "bold white",
    "markdown.h3": "bold yellow",
    "markdown.code": "bright_yellow on grey11",
    "markdown.bullet": "cyan",
    "markdown.link": "underline magenta",
}) if Theme else None


class TerminalUI:
    """Provides styled Rich UI panels, tables, and modal dialogs following the Sympose Design System."""

    @classmethod
    def get_console(cls) -> Optional[Any]:
        if Console is None:
            return None
        return Console(theme=SYMPOSE_THEME)

    @staticmethod
    def display_banner(console: Optional[Any]) -> None:
        if not console:
            print("=== <S> sympose // multi-model agent hub ===")
            return

        banner = Text()
        banner.append("<S>  ", style="bold cyan")
        banner.append("S Y M P O S E  ", style="bold white")
        banner.append("// multi-model agent hub  ", style="dim white")
        banner.append("[v0.2.5]\n", style="dim cyan")
        banner.append("minimalist runtime for macos & slack\n", style="dim white")
        banner.append("commands: /help | /save | /config | switch: /switch | exit: /exit", style="dim cyan")
        console.print(Panel(banner, box=ROUNDED, border_style="cyan", padding=(1, 2)))

    @staticmethod
    def display_setup_banner(console: Optional[Any], workspace_dir: str) -> None:
        if not console:
            print(f"=== <S> sympose // setup wizard ({workspace_dir}) ===")
            return

        banner = Text()
        banner.append("<S>  ", style="bold cyan")
        banner.append("S Y M P O S E  ", style="bold white")
        banner.append("// interactive setup wizard  ", style="dim white")
        banner.append("[v0.2.5]\n", style="dim cyan")
        banner.append("zero-bloat multi-model agent hub & sovereign vault explorer\n\n", style="dim white")
        banner.append("active workspace: ", style="green")
        banner.append(f"{workspace_dir}\n", style="bold yellow")
        banner.append("default persona: ", style="magenta")
        banner.append("@samantha ", style="bold white")
        banner.append("(Polymath Strategic Orchestrator)", style="dim")
        console.print(Panel(banner, box=ROUNDED, border_style="cyan", padding=(1, 2)))

    @staticmethod
    def render_markdown(console: Optional[Any], md_text: str) -> None:
        if not console or Markdown is None:
            print(f"\n{md_text}\n")
            return
        console.print()
        console.print(Markdown(md_text))
        console.print()

    @staticmethod
    def select_persona(console: Optional[Any], profiles: List[Dict[str, Any]], default_handle: str = "samantha") -> str:
        if not profiles or not console:
            return default_handle

        table = Table(title="Personas", box=ROUNDED, border_style="dim cyan", show_header=True, header_style="bold cyan")
        table.add_column("#", style="bold yellow", justify="center", width=4)
        table.add_column("Handle", style="bold yellow")
        table.add_column("Name", style="bold white")
        table.add_column("Role / Title", style="cyan")
        table.add_column("Default Model", style="green")
        table.add_column("Sandbox", style="magenta")

        index_map: Dict[str, str] = {}
        handle_map: Dict[str, str] = {}
        default_choice = default_handle

        for i, p in enumerate(profiles, start=1):
            h = p.get("handle", "").lower()
            index_map[str(i)] = h
            handle_map[h] = h
            handle_map[f"@{h}"] = h
            if h == default_handle.lower():
                default_choice = str(i)

            v_folders = p.get("vault_folders") or ([p["vault_folder"]] if p.get("vault_folder") else [])
            if not v_folders:
                sandbox_desc = "General/"
            elif "*" in v_folders or "" in v_folders or "all" in v_folders:
                sandbox_desc = "Root (*)"
            elif len(v_folders) == 1:
                sandbox_desc = f"{v_folders[0]}/"
            else:
                sandbox_desc = ", ".join(f"{f}/" for f in v_folders[:2]) + (f" (+{len(v_folders)-2})" if len(v_folders) > 2 else "")

            model_display = p.get("model") or os.getenv("DEFAULT_MODEL", "gemini/gemini-3.6-flash")

            table.add_row(
                str(i),
                f"@{p.get('handle')}",
                p.get("name", ""),
                p.get("title", ""),
                model_display,
                sandbox_desc
            )

        console.print(table)
        valid_choices = list(index_map.keys()) + [p["handle"].lower() for p in profiles]
        prompt_label = f"\nSelect persona [1-{len(profiles)} or handle]"
        raw_choice = Prompt.ask(prompt_label, default=default_choice, choices=valid_choices, case_sensitive=False)
        cleaned = raw_choice.lower().replace("@", "").strip()

        if cleaned in index_map:
            return index_map[cleaned]
        if cleaned in handle_map:
            return handle_map[cleaned]
        return default_handle

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
        console.print(Panel(menu_text, box=ROUNDED, title="Save Session Takeaways?", border_style="dim cyan"))

        def_opt = "1" if default_target == "memory" else ("2" if default_target == "obsidian" else ("4" if default_target == "discard" else "3"))
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default=def_opt)

        mapping = {"1": "memory", "2": "obsidian", "3": "both", "4": None}
        return mapping.get(choice)

