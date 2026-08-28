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
        banner.append("[v0.2.19]\n", style="dim cyan")
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
        banner.append("[v0.2.19]\n", style="dim cyan")
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
            print(f"\n{md_text}")
            return
        console.print()
        console.print(Markdown(md_text))

    @staticmethod
    def select_persona(console: Optional[Any], profiles: List[Dict[str, Any]], default_handle: str = "samantha") -> str:
        if not profiles or not console:
            return default_handle

        options = []
        index_map: Dict[str, str] = {}
        handle_map: Dict[str, str] = {}
        default_choice = default_handle

        for i, p in enumerate(profiles, start=1):
            h = p.get("handle", "").lower()
            name = p.get("name", h)
            title = p.get("title", "Specialist Persona")
            index_map[str(i)] = h
            handle_map[h] = h
            handle_map[f"@{h}"] = h
            
            is_active = h == default_handle.lower()
            if is_active:
                default_choice = str(i)
                options.append(f"[bold yellow]@{h}[/bold yellow]  [bold white]{name}[/bold white] [dim]— {title}[/dim] [dim cyan][Active][/dim cyan]")
            else:
                options.append(f"[bold yellow]@{h}[/bold yellow]  [bold white]{name}[/bold white] [dim]— {title}[/dim]")

        TerminalUI.render_option_panel(
            console,
            title="👥  SELECT ACTIVE PERSONA",
            options=options
        )

        valid_choices = list(index_map.keys()) + [p["handle"].lower() for p in profiles] + [f"@{p['handle'].lower()}" for p in profiles]
        prompt_label = f"Select persona [1-{len(profiles)} or @handle]"
        raw_choice = Prompt.ask(prompt_label, default=default_choice, choices=valid_choices, case_sensitive=False)
        cleaned = raw_choice.lower().replace("@", "").strip()

        if cleaned in index_map:
            return index_map[cleaned]
        if cleaned in handle_map:
            return handle_map[cleaned]
        return default_handle

    @staticmethod
    def render_option_panel(
        console: Optional[Any],
        title: str,
        options: List[str],
        subtitle: Optional[str] = None
    ) -> None:
        """Renders a standardized rounded panel containing numbered options."""
        if not console:
            return

        lines = []
        if subtitle:
            lines.append(f"[dim]{subtitle}[/dim]\n")
        for i, opt in enumerate(options, start=1):
            lines.append(f"[bold cyan][{i}][/bold cyan] {opt}")

        panel_content = "\n".join(lines)
        console.print()
        console.print(Panel(
            panel_content,
            box=ROUNDED,
            title=title,
            title_align="left",
            border_style="cyan",
            padding=(0, 2)
        ))

    @staticmethod
    def prompt_exit_choice(console: Optional[Any], handle: str, default_target: str = "both") -> Optional[str]:
        """Displays exit modal dialog for memory/obsidian persistence."""
        if not console:
            return default_target if default_target in ("memory", "obsidian", "both") else None

        console.print(f"\n[bold yellow]Active session with @{handle} detected.[/bold yellow]")
        options = [
            "Memory Only (Append to persistent `_memory.md`)",
            "Obsidian Only (Save structured note to vault)",
            "Both (Memory + Obsidian) [Default]",
            "Discard & Exit (No save)"
        ]
        TerminalUI.render_option_panel(
            console,
            title="💾  SAVE SESSION TAKEAWAYS?",
            options=options
        )

        def_opt = "1" if default_target == "memory" else ("2" if default_target == "obsidian" else ("4" if default_target == "discard" else "3"))
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default=def_opt)

        mapping = {"1": "memory", "2": "obsidian", "3": "both", "4": None}
        return mapping.get(choice)

