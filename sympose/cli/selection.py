"""A reusable numbered, boxed, color-coded selection list — one widget
serving the model, persona, and chat-history pickers, and the
`/`-command autocomplete overlay (see `commands.py` and `app.py`).

Digit keys `1`-`9` select the corresponding row only while this widget
itself holds focus — never globally, and never while the main input has
focus, since a Textual key binding only fires on whichever widget the
key event reaches. That's the same scoping rule the dashboard's numbered
dropdowns use, here it falls out of Textual's own focus-scoped bindings
instead of a capture-phase DOM listener."""

from dataclasses import dataclass

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.widgets import OptionList
from textual.widgets.option_list import Option


@dataclass(frozen=True)
class SelectionOption:
    label: str
    value: str
    # Color-coded $error rather than $primary — a destructive/reset choice
    # (e.g. `/clear`), not a neutral one.
    danger: bool = False


class SelectionPanel(OptionList):
    """Boxed (`border: round`) numbered list, colored from the app's live
    theme (`App.get_css_variables()`) rather than hardcoded ANSI, so a
    theme change repaints this the same way it repaints everything else."""

    DEFAULT_CSS = """
    SelectionPanel {
        border: round $primary;
        height: auto;
        max-height: 12;
        background: $surface;
    }
    SelectionPanel:focus {
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding(str(digit), f"select_digit({digit})", show=False)
        for digit in range(1, 10)
    ]

    def __init__(self, title: str, options: list[SelectionOption], **kwargs) -> None:
        # `_selection_options`, not `_options` — `OptionList.__init__`
        # owns a private `self._options` of its own and would silently
        # clobber a same-named attribute set before `super().__init__()`
        # runs (found live: every panel rendered its border with zero
        # rows until this was renamed).
        self._selection_options = options
        self._title = title
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self.border_title = self._title
        variables = self.app.get_css_variables()
        error_color = variables.get("error", "red")
        primary_color = variables.get("primary", "cyan")
        for index, option in enumerate(self._selection_options, start=1):
            color = error_color if option.danger else primary_color
            label = Text()
            label.append(f" {index} ", style=Style(color="black", bgcolor=color, bold=True))
            label.append(f" {option.label}")
            self.add_option(Option(label, id=option.value))

    def action_select_digit(self, digit: int) -> None:
        index = digit - 1
        if 0 <= index < len(self._selection_options):
            self.highlighted = index
            self.action_select()

    def option_for(self, value: str | None) -> SelectionOption | None:
        return next((o for o in self._selection_options if o.value == value), None)
