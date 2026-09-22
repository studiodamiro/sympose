"""A reusable boxed, color-coded selection list, in two modes:

- **Numbered** (`numbered=True`, the default) — the `/model`/`/persona`/
  `/history` pickers. Each row gets a `[N]` badge; digit keys `1`-`9`
  highlight the corresponding row only while this widget itself holds
  focus — never globally, and never while the main input has focus,
  since a Textual key binding only fires on whichever widget the key
  event reaches.
- **Unnumbered** (`numbered=False`) — the `/`-command autocomplete
  overlay (see `picker.py`). No badges, no digit bindings: that overlay
  is cycled with Tab/Shift+Tab instead (`composer.py`), while the
  `Input` keeps focus so the user can keep typing to filter. Digits are
  reserved for the numbered pickers so "type a number" and "press Tab"
  each mean one specific thing, not two things depending on context."""

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
    """Boxed (`border: round`), colored from the app's live theme
    (`App.get_css_variables()`) rather than hardcoded ANSI, so a theme
    change repaints this the same way it repaints everything else."""

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

    def __init__(
        self,
        title: str,
        options: list[SelectionOption],
        numbered: bool = True,
        initial_highlight: int = -1,
        **kwargs,
    ) -> None:
        # `_selection_options`, not `_options` — `OptionList.__init__`
        # owns a private `self._options` of its own and would silently
        # clobber a same-named attribute set before `super().__init__()`
        # runs (found live: every panel rendered its border with zero
        # rows until this was renamed).
        self._selection_options = options
        self._title = title
        self._numbered = numbered
        self._initial_highlight = initial_highlight
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self.border_title = self._title
        variables = self.app.get_css_variables()
        error_color = variables.get("error", "red")
        primary_color = variables.get("primary", "cyan")
        for index, option in enumerate(self._selection_options, start=1):
            color = error_color if option.danger else primary_color
            label = Text()
            if self._numbered:
                label.append(f" {index} ", style=Style(color="black", bgcolor=color, bold=True))
                label.append(f" {option.label}")
            else:
                label.append(option.label, style=Style(color=color))
            self.add_option(Option(label, id=option.value))
        if 0 <= self._initial_highlight < len(self._selection_options):
            self.highlighted = self._initial_highlight

    def action_select_digit(self, digit: int) -> None:
        # A no-op rather than removing the binding outright when
        # unnumbered — defense in depth, in case this panel ever ends up
        # focused by a path other than `picker.open_picker` (which is
        # the only place that calls `.focus()`, and only for numbered
        # panels). Digits meaning "select" is reserved for those.
        if not self._numbered:
            return
        index = digit - 1
        if 0 <= index < len(self._selection_options):
            self.highlighted = index
            self.action_select()
