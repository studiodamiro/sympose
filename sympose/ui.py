"""
Terminal UI Presentation, Design System & Modals for Sympose.
"""

import random
import threading
import time
from typing import Any

from sympose.config import get_version

try:
    from rich.box import ROUNDED
    from rich.console import Console, Group
    from rich.live import Live
    from rich.markdown import Heading, Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.segment import Segment
    from rich.text import Text
    from rich.theme import Theme

    if Heading and hasattr(Heading, "LEVEL_ALIGN"):
        Heading.LEVEL_ALIGN["h1"] = "left"
except ImportError:
    Console = None
    Group = None
    Rule = None
    Segment = None
    ROUNDED = None
    Markdown = None
    Heading = None
    Live = None

SYMPOSE_THEME = (
    Theme(
        {
            "sympose.brand": "bold cyan",
            "sympose.user": "bold yellow",
            "sympose.persona": "bold cyan",
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
        }
    )
    if Theme
    else None
)


class AnimatedStatus:
    """Wraps a rich `Status` and cycles its text through a phrase pool while
    it runs, instead of holding one static line for the whole wait.

    Purely cosmetic terminal presentation — it does not touch the model
    stream, add a round-trip, or cost a token; it only changes what the
    spinner says while we're already waiting on the first chunk. Drop-in
    replacement for `console.status(...)`: exposes the same `.start()` /
    `.stop()` interface so existing call sites don't need to change.
    """

    def __init__(self, console, name: str, phrases: list[str], interval: float = 1.7):
        self._phrases = list(phrases) if phrases else ["Thinking..."]
        self._name = name
        self._interval = interval
        self._status = console.status(
            self._render(random.choice(self._phrases)), spinner="dots"
        )
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._cycle, daemon=True)

    def _render(self, phrase: str) -> str:
        return f"[dim italic cyan]{self._name} is {phrase.lower()}[/dim italic cyan]"

    def start(self):
        self._status.start()
        if len(self._phrases) > 1:
            self._thread.start()
        return self

    def _cycle(self):
        last = None
        while not self._stop_event.wait(self._interval):
            choices = [p for p in self._phrases if p != last] or self._phrases
            phrase = random.choice(choices)
            last = phrase
            try:
                self._status.update(self._render(phrase))
            except Exception:
                return

    def stop(self):
        self._stop_event.set()
        self._status.stop()


class MultiSectionPanel:
    """Rich renderable that draws a rounded box with multiple sections and inline T-junction headers."""

    def __init__(
        self,
        title: str,
        sections: list[tuple[str | None, Any]],
        border_style: str = "cyan",
        padding: tuple[int, int] = (1, 2),
    ):
        self.title = title
        self.sections = sections
        self.border_style = border_style
        self.padding = padding

    def _render_top_border(self, console: Any, width: int, border_style: Any) -> Any:
        top_title = Text.from_markup(f" {self.title} ") if self.title else Text("")
        top_title_len = top_title.cell_len
        left_border_len = 1
        right_border_len = max(width - 2 - left_border_len - top_title_len, 1)

        yield Segment("╭─", border_style)
        for seg in top_title.render(console):
            yield seg
        yield Segment("─" * right_border_len + "╮\n", border_style)

    def _render_padding_row(self, width: int, border_style: Any) -> Any:
        yield Segment("│" + " " * (width - 2) + "│\n", border_style)

    def _render_section_separator(
        self, console: Any, width: int, s_title: str | None, border_style: Any
    ) -> Any:
        if s_title:
            mid_title = Text.from_markup(f" {s_title} ")
            mid_len = mid_title.cell_len
            mid_right_len = max(width - 2 - 1 - mid_len, 1)
            yield Segment("├─", border_style)
            for seg in mid_title.render(console):
                yield seg
            yield Segment("─" * mid_right_len + "┤\n", border_style)
        else:
            yield Segment("├" + "─" * (width - 2) + "┤\n", border_style)

    def _render_section_body(
        self,
        console: Any,
        options: Any,
        s_renderable: Any,
        inner_width: int,
        pad_str: str,
        border_style: Any,
    ) -> Any:
        child_options = options.update_width(inner_width)
        lines = console.render_lines(s_renderable, child_options, pad=False)
        for line in lines:
            line_len = (
                Segment.get_line_length(line)
                if Segment
                else sum(len(s.text) for s in line)
            )
            right_pad = max(inner_width - line_len, 0)
            yield Segment("│" + pad_str, border_style)
            for seg in line:
                yield seg
            yield Segment(" " * right_pad + pad_str + "│\n", border_style)

    def __rich_console__(self, console: Any, options: Any) -> Any:
        width = options.max_width or 80
        inner_width = max(width - 2 - (self.padding[1] * 2), 10)
        border_style = console.get_style(self.border_style)
        pad_str = " " * self.padding[1]

        yield from self._render_top_border(console, width, border_style)
        if self.padding[0] > 0:
            yield from self._render_padding_row(width, border_style)

        for s_idx, (s_title, s_renderable) in enumerate(self.sections):
            if s_idx > 0:
                if self.padding[0] > 0:
                    yield from self._render_padding_row(width, border_style)
                yield from self._render_section_separator(
                    console, width, s_title, border_style
                )
                if self.padding[0] > 0:
                    yield from self._render_padding_row(width, border_style)

            yield from self._render_section_body(
                console, options, s_renderable, inner_width, pad_str, border_style
            )

        # Padding bottom if requested
        if self.padding[0] > 0:
            yield from self._render_padding_row(width, border_style)

        # Bottom border: ╰────────────╯
        yield Segment("╰" + "─" * (width - 2) + "╯\n", border_style)


class TerminalUI:
    """Provides styled Rich UI panels, tables, and modal dialogs following the Sympose Design System."""

    @classmethod
    def get_console(cls) -> Any | None:
        if Console is None:
            return None
        return Console(theme=SYMPOSE_THEME)

    @staticmethod
    def display_banner(console: Any | None) -> None:
        if not console:
            print("=== <S> sympose // multi-model persona hub ===")
            return

        banner = Text()
        banner.append("<S>  ", style="bold cyan")
        banner.append("S Y M P O S E  ", style="bold white")
        banner.append("// multi-model persona hub  ", style="dim white")
        banner.append(f"[v{get_version()}]\n", style="dim cyan")
        banner.append(
            "gives your Obsidian vault a voice — zero-bloat & local-first\n", style="dim white"
        )
        banner.append(
            "commands: /help | /save | /config | switch: /switch | exit: /exit",
            style="dim cyan",
        )
        console.print(Panel(banner, box=ROUNDED, border_style="cyan", padding=(1, 2)))

    @staticmethod
    def display_setup_banner(console: Any | None, workspace_dir: str) -> None:
        if not console:
            print(f"=== <S> sympose // setup wizard ({workspace_dir}) ===")
            return

        banner = Text()
        banner.append("<S>  ", style="bold cyan")
        banner.append("S Y M P O S E  ", style="bold white")
        banner.append("// interactive setup wizard  ", style="dim white")
        banner.append(f"[v{get_version()}]\n", style="dim cyan")
        banner.append(
            "zero-bloat multi-model persona hub & sovereign vault explorer\n\n",
            style="dim white",
        )
        banner.append("active workspace: ", style="green")
        banner.append(f"{workspace_dir}\n", style="bold yellow")
        banner.append("default persona: ", style="magenta")
        banner.append("@samantha ", style="bold white")
        banner.append("(Polymath Strategic Orchestrator)", style="dim")
        console.print(Panel(banner, box=ROUNDED, border_style="cyan", padding=(1, 2)))

    @staticmethod
    def render_markdown(console: Any | None, md_text: str) -> None:
        if not console or Markdown is None:
            print(f"\n{md_text}")
            return
        console.print()
        console.print(Markdown(md_text))

    @staticmethod
    def render_markdown_typewriter(
        console: Any | None,
        md_text: str,
        duration: float = 1.4,
        min_len_for_effect: int = 24,
    ) -> None:
        """Reveal a completed Markdown reply progressively instead of dumping
        it all at once — `buffered` render mode already holds the whole reply
        in memory before drawing anything, so the "wait, then everything at
        once" moment is what reads as slow, not the actual generation time.

        Bounded to `duration` seconds total no matter how long the reply is
        (a long answer doesn't typewriter any slower than a short one), and
        reveals in a handful of chunks rather than truly one character at a
        time, so a long reply isn't re-parsed as Markdown thousands of times.
        Falls back to an instant render for short replies, non-terminal
        output (piping, redirected stdout), or if Live/Markdown aren't
        available — the animation is cosmetic, never a dependency.
        """
        is_tty = bool(console and getattr(console, "is_terminal", False))
        if (
            not console
            or Markdown is None
            or Live is None
            or not is_tty
            or len(md_text) < min_len_for_effect
        ):
            TerminalUI.render_markdown(console, md_text)
            return

        steps = max(1, min(120, len(md_text) // 3))
        chunk_size = max(1, -(-len(md_text) // steps))  # ceil division

        console.print()
        try:
            start = time.time()
            with Live(
                Markdown(""), console=console, refresh_per_second=30, transient=False
            ) as live:
                for step, i in enumerate(range(0, len(md_text), chunk_size), start=1):
                    live.update(Markdown(md_text[: i + chunk_size]))
                    # Sleep only enough to stay on the `duration` schedule —
                    # each step's own Markdown-parse/diff overhead eats into
                    # the budget too, so a fixed per-step sleep would drift
                    # past `duration` on longer replies with more steps.
                    remaining = (start + (step / steps) * duration) - time.time()
                    if remaining > 0:
                        time.sleep(remaining)
                live.update(Markdown(md_text))
        except KeyboardInterrupt:
            raise
        except Exception:
            console.print(Markdown(md_text))

    @staticmethod
    def select_persona(
        console: Any | None,
        profiles: list[dict[str, Any]],
        default_handle: str = "samantha",
    ) -> str:
        if not profiles or not console:
            return default_handle

        options = []
        index_map: dict[str, str] = {}
        handle_map: dict[str, str] = {}
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
                options.append(
                    f"[bold yellow]@{h}[/bold yellow]  [bold white]{name}[/bold white] [dim]— {title}[/dim] [dim cyan][Active][/dim cyan]"
                )
            else:
                options.append(
                    f"[bold yellow]@{h}[/bold yellow]  [bold white]{name}[/bold white] [dim]— {title}[/dim]"
                )

        TerminalUI.render_option_panel(
            console, title="👥  SELECT ACTIVE PERSONA", options=options
        )

        prompt_label = f"\n[bold cyan]Select persona[/bold cyan] [dim][1-{len(profiles)} or @handle, Enter for default][/dim]"
        try:
            raw_choice = Prompt.ask(
                prompt_label,
                default=default_choice,
                show_choices=False,
                show_default=False,
            )
        except (KeyboardInterrupt, EOFError):
            return default_handle

        cleaned = (
            raw_choice.lower().replace("@", "").strip()
            if raw_choice
            else default_choice
        )

        if cleaned in index_map:
            return index_map[cleaned]
        if cleaned in handle_map:
            return handle_map[cleaned]
        return default_handle

    @staticmethod
    def render_option_panel(
        console: Any | None,
        title: str,
        options: list[str],
        subtitle: str | None = None,
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
        console.print(
            Panel(
                panel_content,
                box=ROUNDED,
                title=title,
                title_align="left",
                border_style="cyan",
                padding=(0, 2),
            )
        )

    @staticmethod
    def prompt_exit_choice(
        console: Any | None, handle: str, default_target: str = "memory"
    ) -> str | None:
        """Displays exit modal dialog for memory persistence."""
        if not console:
            return "memory" if default_target == "memory" else None

        console.print(
            f"\n[bold yellow]Active session with @{handle} completed.[/bold yellow]"
        )
        options = [
            "Extract durable facts to `_memory.md` [Default]",
            "Skip (Preserve in `/history` only)",
        ]
        TerminalUI.render_option_panel(
            console, title="🧠  SAVE WORKING MEMORY?", options=options
        )

        def_opt = "1" if default_target == "memory" else "2"
        prompt_label = (
            "\n[bold cyan]Select option[/bold cyan] [dim][1-2, Enter for [1]][/dim]"
        )
        try:
            choice = Prompt.ask(
                prompt_label, default=def_opt, show_choices=False, show_default=False
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return "memory" if default_target == "memory" else None

        return "memory" if choice == "1" else None

    @staticmethod
    def _select_session_plain(sessions: list[dict[str, Any]], show_handle: bool) -> str:
        print("\n=== CONVERSATION HISTORY ===")
        for i, s in enumerate(sessions, start=1):
            h_str = f"@{s.get('handle', '')} • " if show_handle else ""
            print(
                f'[{i}] "{s.get("title", "Untitled")}" ({h_str}{s.get("relative_time", "")}, {s.get("turns_count", 0)} turns)'
            )
        raw = input(f"Select session [1-{len(sessions)} or Enter for 1]: ").strip()
        idx = int(raw) - 1 if raw.isdigit() and 1 <= int(raw) <= len(sessions) else 0
        return sessions[idx]["session_id"]

    @staticmethod
    def _build_session_lines(
        sessions: list[dict[str, Any]],
        active_session_id: str | None,
        show_handle: bool,
    ) -> tuple[list[str], dict[str, str]]:
        lines = []
        index_map: dict[str, str] = {}
        for i, s in enumerate(sessions, start=1):
            sid = s.get("session_id", "")
            index_map[str(i)] = sid
            index_map[sid] = sid

            title = s.get("title", "Untitled Session")
            r_time = s.get("relative_time", "Recent")
            turns_cnt = s.get("turns_count", 0)
            is_active = sid == active_session_id
            h_tag = s.get("handle", "")

            # Line 1: [i] "Title"
            lines.append(
                f'[bold cyan][{i}][/bold cyan] [bold white]"{title}"[/bold white]'
            )

            # Line 2: Details metadata indented
            meta_parts = []
            if show_handle and h_tag:
                meta_parts.append(f"[bold cyan]@{h_tag}[/bold cyan]")
            meta_parts.append(
                f"[dim]{r_time}  •  {turns_cnt} turn{'s' if turns_cnt != 1 else ''}[/dim]"
            )
            if is_active:
                meta_parts.append("[bold cyan][Active][/bold cyan]")

            meta_str = f"    {'  •  '.join(meta_parts) if not (show_handle and h_tag) else '  '.join(meta_parts)}"
            lines.append(meta_str)
            if i < len(sessions):
                lines.append("")
        return lines, index_map

    @staticmethod
    def _session_title_header(handle: str | None, show_handle: bool) -> str:
        if show_handle:
            return "📜  ALL CONVERSATIONS"
        if handle:
            return f"📜  CONVERSATION HISTORY (@{handle})"
        return "📜  CONVERSATION HISTORY"

    @staticmethod
    def _resolve_session_choice(
        raw_choice: str | None,
        sessions: list[dict[str, Any]],
        index_map: dict[str, str],
    ) -> str | None:
        cleaned = raw_choice.strip().lower() if raw_choice else "1"
        if cleaned in ("q", "cancel", "exit", ":q"):
            return None
        if not cleaned or cleaned == "1":
            return sessions[0]["session_id"]
        if cleaned in index_map:
            return index_map[cleaned]
        return sessions[0]["session_id"]

    @staticmethod
    def select_session(
        console: Any | None,
        sessions: list[dict[str, Any]],
        active_session_id: str | None = None,
        handle: str | None = None,
        show_handle: bool = False,
    ) -> str | None:
        """Renders an interactive session selector panel and returns chosen session_id or None."""
        if not sessions:
            if console:
                console.print(
                    f"[dim yellow]No past conversation sessions found{' for @' + handle if handle else ''}.[/dim yellow]"
                )
            else:
                print("No past conversation sessions found.")
            return None

        if not console:
            return TerminalUI._select_session_plain(sessions, show_handle)

        lines, index_map = TerminalUI._build_session_lines(
            sessions, active_session_id, show_handle
        )
        panel_content = "\n".join(lines)
        console.print()
        console.print(
            Panel(
                panel_content,
                box=ROUNDED,
                title=TerminalUI._session_title_header(handle, show_handle),
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        prompt_label = f"\n[bold cyan]Select session to resume[/bold cyan] [dim][1-{len(sessions)}, Enter for [1], 'q' to cancel][/dim]"
        try:
            raw_choice = Prompt.ask(
                prompt_label, default="1", show_choices=False, show_default=False
            )
        except (KeyboardInterrupt, EOFError):
            return None

        return TerminalUI._resolve_session_choice(raw_choice, sessions, index_map)

    @staticmethod
    def select_render_mode(
        console: Any | None, current_mode: str = "hybrid"
    ) -> str | None:
        """Renders the standard render mode selection box and returns the chosen mode or None."""
        modes = [
            (
                "1",
                "hybrid",
                "Smart Hybrid (Recommended)",
                "Prose streams word-by-word (<0.5s TTFT) • Sub-agent reports rendered with Rich Markdown",
            ),
            (
                "2",
                "buffered",
                "Full Buffered Markdown",
                "Waits 1-2s for completion • 100% pixel-perfect Rich Markdown everywhere",
            ),
            (
                "3",
                "raw",
                "Raw Terminal Transparency",
                "Direct stdout streaming • Zero formatting overhead",
            ),
        ]

        if not console:
            print("\n=== TERMINAL RENDER MODE ===")
            for num, key, title, desc in modes:
                is_active = " [Active]" if key == current_mode.lower() else ""
                print(f'[{num}] "{title}"{is_active}\n    {desc}\n')
            raw = (
                input("Select render mode [1-3, Enter for 1, 'q' to cancel]: ")
                .strip()
                .lower()
            )
            if raw in ("q", "cancel"):
                return None
            mode_map = {
                "1": "hybrid",
                "2": "buffered",
                "3": "raw",
                "hybrid": "hybrid",
                "buffered": "buffered",
                "raw": "raw",
            }
            return mode_map.get(raw, "hybrid")

        lines = []
        for num, key, title, desc in modes:
            is_active = key == current_mode.lower()
            active_chip = "  [bold cyan][Active][/bold cyan]" if is_active else ""
            lines.append(
                f'[bold cyan][{num}][/bold cyan] [bold white]"{title}"[/bold white]{active_chip}'
            )
            lines.append(f"    [dim]{desc}[/dim]")
            if num != "3":
                lines.append("")

        panel = Panel(
            "\n".join(lines),
            box=ROUNDED,
            title="🎨  TERMINAL RENDER MODE",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print()
        console.print(panel)

        prompt_label = "\n[bold cyan]Select render mode[/bold cyan] [dim][1-3, Enter for [1], 'q' to cancel][/dim]"
        try:
            raw_choice = Prompt.ask(
                prompt_label, default="1", show_choices=False, show_default=False
            )
        except (KeyboardInterrupt, EOFError):
            return None

        cleaned = raw_choice.strip().lower() if raw_choice else "1"
        if cleaned in ("q", "cancel", "exit", ":q"):
            return None

        mode_map = {
            "1": "hybrid",
            "hybrid": "hybrid",
            "smart": "hybrid",
            "2": "buffered",
            "buffered": "buffered",
            "full": "buffered",
            "markdown": "buffered",
            "3": "raw",
            "raw": "raw",
            "plain": "raw",
        }
        return mode_map.get(cleaned, "hybrid")

    @staticmethod
    def render_session_resumed(
        console: Any | None,
        session_title: str,
        handle: str,
        replay_turns: list[dict[str, Any]],
    ) -> None:
        """Renders the resumed session banner and past turns in dimmed Markdown."""
        if not console:
            print(f'\n─── 🔄 Resumed Session: @{handle} ("{session_title}") ───')
            for t in replay_turns:
                print(f"You: {t.get('user', '')}")
                print(f"@{handle}: {t.get('assistant', '')}\n")
            print("─" * 60)
            return

        console.print()
        banner_text = f'[dim cyan]─── 🔄 Resumed Session: [bold cyan]@{handle}[/bold cyan] [bold white]"{session_title}"[/bold white] ──────────────────────────[/dim cyan]'
        console.print(banner_text)

        for t in replay_turns:
            u_msg = t.get("user", "").strip()
            a_msg = t.get("assistant", "").strip()
            if u_msg:
                console.print(
                    f"\n[bold yellow]You[/bold yellow]: [dim white]{u_msg}[/dim white]"
                )
            if a_msg:
                console.print(f"\n[bold cyan]@{handle}[/bold cyan]:")
                console.print(Markdown(a_msg))

        console.print(
            "\n[dim cyan]──────────────────────────────────────────────────────────────────────────[/dim cyan]\n"
        )

    @staticmethod
    def _print_plain_search_results(query: str, results: list[dict[str, Any]]) -> None:
        print(f'\n=== VAULT SEARCH: "{query}" ({len(results)} matches) ===')
        for r in results:
            idx = r.get("index", 1)
            rel = r.get("rel_path", r.get("file_name", ""))
            mtype = r.get("match_type", "content")
            l_no = r.get("line_no", 1)
            type_str = "Title Match" if mtype == "title" else f"Line {l_no}"
            print(f"[{idx}] {rel} ({type_str})")
            if r.get("snippet"):
                print(f"    > {r['snippet']}")

    @staticmethod
    def _build_search_result_lines(i: int, r: dict[str, Any], total: int) -> list[str]:
        rel = r.get("rel_path", r.get("file_name", "note.md"))
        mtype = r.get("match_type", "content")
        line_no = r.get("line_no", 1)
        snippet = r.get("snippet", "")
        tags = r.get("tags", [])

        badge_str = f'[bold cyan][{i}][/bold cyan] [bold white]"{rel}"[/bold white]'
        type_str = (
            "[bold green]Title Match[/bold green]"
            if mtype == "title"
            else f"[dim yellow]Line {line_no}[/dim yellow]"
        )

        lines = [f"{badge_str}  [dim]({type_str})[/dim]"]

        if tags:
            chips = [f"[bold yellow]#{t.lstrip('#')}[/bold yellow]" for t in tags[:6]]
            lines.append(f"    {' '.join(chips)}")

        if snippet:
            clean_snip = " ".join(snippet.split())
            if len(clean_snip) > 70:
                clean_snip = clean_snip[:67].rstrip() + "..."
            lines.append(
                f"    [dim cyan]>[/dim cyan] [dim white]{clean_snip}[/dim white]"
            )

        if i < total:
            lines.append("")
        return lines

    @staticmethod
    def _search_nav_hint(count: int) -> list[str]:
        return [
            "",
            "[dim cyan]──────────────────────────────────────────────────────────────────────────[/dim cyan]",
            f"[dim]Quick Nav: [bold cyan]1-{count}[/bold cyan] to view in terminal  •  [bold cyan]o <#>[/bold cyan] to open in Obsidian  •  [bold cyan]q[/bold cyan] to exit[/dim]",
        ]

    @staticmethod
    def render_vault_search_panel(
        console: Any | None,
        query: str,
        results: list[dict[str, Any]],
        show_nav_hint: bool = True,
    ) -> None:
        """Renders an orderly, high-density Rich panel containing vault search results."""
        if not results:
            if console:
                console.print(
                    f'\n[dim yellow]No notes found matching "{query}" in allowed vault folders.[/dim yellow]\n'
                )
            else:
                print(
                    f'\nNo notes found matching "{query}" in allowed vault folders.\n'
                )
            return

        if not console:
            TerminalUI._print_plain_search_results(query, results)
            return

        lines = []
        for i, r in enumerate(results, start=1):
            lines.extend(TerminalUI._build_search_result_lines(i, r, len(results)))

        if show_nav_hint:
            lines.extend(TerminalUI._search_nav_hint(len(results)))

        panel_content = "\n".join(lines)
        console.print()
        console.print(
            Panel(
                panel_content,
                box=ROUNDED,
                title=f'🔍  VAULT SEARCH: "{query}" ({len(results)} match{"es" if len(results) != 1 else ""})',
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    @staticmethod
    def render_sub_agent_report_panel(
        console: Any | None,
        task: str,
        skills: list[str],
        tool_calls: list[str],
        deliverables: str,
    ) -> None:
        """Renders Sub-Agent Report inside a vibrant styled Rich panel."""
        if not console or Markdown is None:
            print(f"\n=== SUB-AGENT REPORT ({', '.join(skills)}) ===")
            print(f"Task: {task}")
            if tool_calls:
                for tc in tool_calls:
                    print(f"  Tool: {tc}")
            print("-" * 40)
            print(deliverables)
            print("=" * 60 + "\n")
            return

        skill_chips = (
            " ".join([f"[bold cyan]#{s}[/bold cyan]" for s in skills])
            if skills
            else "[dim]default[/dim]"
        )
        body_lines = []
        if tool_calls:
            for tc in tool_calls:
                body_lines.append(
                    f"[dim]⚙️  [dim yellow]Tool:[/dim yellow] [bold white]{tc}[/bold white][/dim]"
                )
            body_lines.append("")

        panel_title = f"[bold yellow]🛠️  SUB-AGENT REPORT[/bold yellow]  [dim]•[/dim]  {skill_chips}"
        content = (
            f"[bold white]Task:[/bold white] [italic]{task}[/italic]\n\n"
            + ("\n".join(body_lines) if body_lines else "")
            + deliverables.strip()
        )

        panel = Panel(
            content,
            box=ROUNDED,
            title=panel_title,
            title_align="left",
            border_style="yellow",
            padding=(1, 2),
        )
        console.print()
        console.print(panel)

    @staticmethod
    def _print_plain_note(rel_path: str, meta: dict[str, Any], body: str) -> None:
        print(f"\n=== NOTE: {rel_path} ===")
        if meta:
            print("Frontmatter:")
            for k, v in meta.items():
                print(f"  {k}: {v}")
            print("-" * 40)
        print(body)
        print("=" * 60 + "\n")

    @staticmethod
    def _note_stats_text(rel_path: str, full_content: str) -> Any:
        lines_count = len(full_content.splitlines())
        size_bytes = len(full_content.encode("utf-8"))
        size_str = (
            f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
        )
        return Text.from_markup(
            f"[dim cyan]Path:[/dim cyan] [bold white]{rel_path}[/bold white]  [dim]•[/dim]  [dim cyan]Lines:[/dim cyan] [dim]{lines_count}[/dim]  [dim]•[/dim]  [dim cyan]Size:[/dim cyan] [dim]{size_str}[/dim]"
        )

    @staticmethod
    def _normalize_frontmatter_tags(tags_val: Any) -> list[str]:
        if isinstance(tags_val, str):
            return [
                t.strip() for t in tags_val.replace(",", " ").split() if t.strip()
            ]
        if isinstance(tags_val, list):
            return [str(t).strip() for t in tags_val if str(t).strip()]
        return [str(tags_val)]

    @staticmethod
    def _frontmatter_extra_field_line(k: str, v: Any) -> str | None:
        if k.lower() in ("title", "name", "tags"):
            return None
        if v is None or v == "" or v == [] or str(v).lower() in ("none", "null", "[]"):
            return None
        v_str = (
            ", ".join(str(x) for x in v if str(x).strip())
            if isinstance(v, list)
            else str(v)
        )
        if not v_str:
            return None
        k_label = k.replace("_", " ").capitalize()
        return f"[bold cyan]{k_label}:[/bold cyan] [dim white]{v_str}[/dim white]"

    @staticmethod
    def _build_frontmatter_lines(meta: dict[str, Any]) -> list[str]:
        fm_lines = []
        title_val = meta.get("title") or meta.get("name")
        if title_val:
            fm_lines.append(
                f"[bold cyan]Title:[/bold cyan] [bold white]{title_val}[/bold white]"
            )

        tags_val = meta.get("tags")
        if tags_val:
            tag_list = TerminalUI._normalize_frontmatter_tags(tags_val)
            chips = " ".join(
                [f"[bold yellow]#{t.lstrip('#')}[/bold yellow]" for t in tag_list]
            )
            fm_lines.append(f"[bold cyan]Tags:[/bold cyan] {chips}")

        for k, v in meta.items():
            line = TerminalUI._frontmatter_extra_field_line(k, v)
            if line:
                fm_lines.append(line)
        return fm_lines

    @staticmethod
    def render_vault_note_panel(
        console: Any | None,
        rel_path: str,
        full_content: str,
        abs_path: str | None = None,
    ) -> None:
        """Renders note content inside a styled Rich box with inline T-junction headers and colorized YAML frontmatter."""
        from sympose.vault import VaultManager

        meta, body = VaultManager.parse_frontmatter(full_content)

        if not console or Markdown is None:
            TerminalUI._print_plain_note(rel_path, meta, body)
            return

        # Section 1: Stats Bar
        sections = [(None, TerminalUI._note_stats_text(rel_path, full_content))]

        # Section 2: Frontmatter (with ├─ 🏷️ FRONTMATTER ────┤ divider)
        if meta:
            fm_lines = TerminalUI._build_frontmatter_lines(meta)
            s2 = Text.from_markup("\n".join(fm_lines))
            sections.append(("[bold yellow]🏷️  FRONTMATTER[/bold yellow]", s2))

        # Section 3: Markdown Body (with ├────────────────────┤ divider)
        s3 = Markdown(body.strip() if body.strip() else "*(Empty note)*")
        sections.append((None, s3))

        panel = MultiSectionPanel(
            title=f"[bold cyan]📄  NOTE:[/bold cyan] [bold white]{rel_path}[/bold white]",
            sections=sections,
            border_style="cyan",
            padding=(1, 2),
        )

        console.print()
        console.print(panel)

    @classmethod
    def _open_result_in_obsidian(cls, console: Any, profile: dict[str, Any], rel_path: str) -> None:
        from sympose.vault import VaultManager

        ok, msg = VaultManager.open_in_obsidian(profile, rel_path)
        console.print(
            f"\n[bold green]✓ {msg}[/bold green]\n"
            if ok
            else f"\n[bold red]⚠️ {msg}[/bold red]\n"
        )

    @staticmethod
    def _print_invalid_index(console: Any, num_results: int) -> None:
        console.print(
            f"\n[dim yellow]Invalid note index. Please select 1-{num_results}.[/dim yellow]\n"
        )

    @classmethod
    def _handle_list_open_command(
        cls,
        console: Any,
        profile: dict[str, Any],
        results: list[dict[str, Any]],
        raw: str,
        current_index: int,
        num_results: int,
    ) -> None:
        target_idx = current_index
        parts = raw.split()
        if len(parts) > 1 and parts[1].isdigit():
            target_idx = int(parts[1])
        elif len(raw) > 1 and raw[1:].isdigit():
            target_idx = int(raw[1:])

        if 1 <= target_idx <= num_results:
            cls._open_result_in_obsidian(
                console, profile, results[target_idx - 1]["rel_path"]
            )
        else:
            cls._print_invalid_index(console, num_results)

    @classmethod
    def _run_list_mode_turn(
        cls,
        console: Any,
        profile: dict[str, Any],
        query: str,
        results: list[dict[str, Any]],
        current_index: int,
        num_results: int,
    ) -> tuple[str, int, bool]:
        """One list-mode prompt/response cycle. Returns (view_mode,
        current_index, should_stop)."""
        cls.render_vault_search_panel(console, query, results, show_nav_hint=False)
        prompt_label = f"\n[bold cyan]Select note[/bold cyan] [dim][1-{num_results}, 'o <#>' to open in Obsidian, 'q' to exit][/dim]"
        try:
            raw = (
                Prompt.ask(prompt_label, default="1", show_choices=False, show_default=False)
                .strip()
                .lower()
            )
        except (KeyboardInterrupt, EOFError):
            return "list", current_index, True

        if raw in ("q", "quit", "exit", "cancel", ":q"):
            return "list", current_index, True

        if raw.startswith("o"):
            cls._handle_list_open_command(
                console, profile, results, raw, current_index, num_results
            )
            return "list", current_index, False

        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= num_results:
                return "note", idx, False
            cls._print_invalid_index(console, num_results)
            return "list", current_index, False

        if not raw:
            return "note", 1, False

        console.print(
            f"\n[dim yellow]Unrecognized input. Enter 1-{num_results}, 'o <#>', or 'q'.[/dim yellow]\n"
        )
        return "list", current_index, False

    @classmethod
    def _run_note_mode_turn(
        cls,
        console: Any,
        profile: dict[str, Any],
        results: list[dict[str, Any]],
        current_index: int,
        num_results: int,
    ) -> tuple[str, int, bool]:
        """One note-mode prompt/response cycle. Returns (view_mode,
        current_index, should_stop)."""
        from sympose.vault import VaultManager

        target_item = results[current_index - 1]
        rel_path = target_item["rel_path"]
        full_content = VaultManager.read_note(profile, rel_path)
        cls.render_vault_note_panel(
            console, rel_path, full_content, abs_path=target_item.get("abs_path")
        )

        prompt_label = f"\n[bold cyan]Select[/bold cyan] [dim][1-{num_results}: jump | o: open in Obsidian | b: back to list | q: exit][/dim]"
        try:
            raw = (
                Prompt.ask(prompt_label, default="b", show_choices=False, show_default=False)
                .strip()
                .lower()
            )
        except (KeyboardInterrupt, EOFError):
            return "note", current_index, True

        if raw in ("q", "quit", "exit", "cancel", ":q"):
            return "note", current_index, True
        if raw in ("b", "back", "list"):
            return "list", current_index, False
        if raw in ("o", "open"):
            cls._open_result_in_obsidian(console, profile, rel_path)
            return "note", current_index, False
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= num_results:
                return "note", idx, False
            cls._print_invalid_index(console, num_results)
            return "note", current_index, False
        if not raw:
            return "list", current_index, False

        console.print(
            f"\n[dim yellow]Unrecognized input. Enter 1-{num_results}, 'o', 'b', or 'q'.[/dim yellow]\n"
        )
        return "note", current_index, False

    @classmethod
    def interactive_vault_browser(
        cls,
        console: Any | None,
        profile: dict[str, Any],
        query: str,
        results: list[dict[str, Any]],
        initial_index: int | None = None,
    ) -> None:
        """Interactive browser loop for navigating search results, viewing notes, and opening in Obsidian."""
        from sympose.vault import VaultManager

        if not results:
            if console:
                console.print(
                    f'\n[dim yellow]No notes found matching "{query}" in allowed vault folders.[/dim yellow]\n'
                )
            else:
                print(f'\nNo notes found matching "{query}".\n')
            return

        if not console or Prompt is None:
            print(VaultManager.format_search_digest(query, results))
            return

        view_mode = "note" if initial_index is not None else "list"
        current_index = initial_index if initial_index is not None else 1
        num_results = len(results)

        while True:
            if view_mode == "list":
                view_mode, current_index, should_stop = cls._run_list_mode_turn(
                    console, profile, query, results, current_index, num_results
                )
            else:
                view_mode, current_index, should_stop = cls._run_note_mode_turn(
                    console, profile, results, current_index, num_results
                )
            if should_stop:
                break
