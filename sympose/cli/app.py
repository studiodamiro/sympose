"""The Textual app shell: a persistent, always-live `Input` docked at the
bottom with a scrolling transcript above it — the one thing legacy's
blocking `rich.prompt.Prompt` loop couldn't do (see `docs/VISION.md`,
lines 46-50). No `PersonaEngine` wired in yet: replies are canned
(`mock_data.py`), and every slash command is inert or mock this pass.
Event handling and the actual command/streaming behavior live in
`dispatch.py`/`runtime.py`/`picker.py`, split out to hold the
200-LOC-per-file cap."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Input, OptionList, Static

from sympose.cli import dispatch, picker
from sympose.cli import transcript as transcript_mod
from sympose.cli.composer import ComposerInput
from sympose.cli.mock_data import MOCK_MODELS, list_personas
from sympose.cli.selection import SelectionPanel


class SymposeCLI(App):
    """Run with `python -m sympose.cli`."""

    CSS = """
    Screen {
        background: $surface;
    }
    #banner {
        border: round $primary;
        height: auto;
        padding: 0 1;
        margin: 0 1 1 1;
    }
    #transcript {
        height: 1fr;
        margin: 0 1;
    }
    .turn-gap {
        margin-top: 1;
    }
    SelectionPanel {
        margin: 0 1;
    }
    #composer {
        border: round $primary;
        margin: 1 1 1 1;
    }
    #composer:focus {
        border: round $accent;
    }
    """

    BINDINGS = [Binding("escape", "close_panel", "Close picker", show=False)]

    def compose(self) -> ComposeResult:
        yield Static("", id="banner")
        yield VerticalScroll(id="transcript")
        yield ComposerInput(placeholder="Message… (/ for commands)", id="composer")

    def on_mount(self) -> None:
        personas = list_personas()
        # Samantha is the only persona that ships as a product default
        # (see `CLAUDE.md`'s project rules) — pick her explicitly rather
        # than whichever profile happens to sort first alphabetically.
        self.persona = next((p for p in personas if p.handle == "samantha"), personas[0])
        self.model = MOCK_MODELS[0]
        self.panel: SelectionPanel | None = None
        self.panel_kind: str | None = None
        self.reply_count = 0
        self.reply_timer = None
        # Tab/Shift+Tab cycle-and-fill state for the `/`-autocomplete
        # overlay (see `composer.py`/`picker.py`); `None` means no
        # cycle session is active (last edit was real typing, not Tab).
        self.tab_matches = None
        self.tab_index = -1
        self.filling_tab_count = 0
        # Tracks which "chatter" (user / persona / system) mounted the
        # last transcript line — `transcript.py`'s `mount_line` only adds
        # a gap above a line when this changes, so consecutive lines
        # from the same speaker stay grouped together.
        self.last_speaker: str | None = None
        picker.update_banner(self)
        transcript_mod.mount_line(
            self, "Mock CLI — canned replies only, no engine wired in yet.", "system"
        )
        transcript_mod.mount_line(self, "Type a message, or / for commands.", "system")
        self.composer.focus()

    @property
    def transcript(self) -> VerticalScroll:
        return self.query_one("#transcript", VerticalScroll)

    @property
    def composer(self) -> Input:
        return self.query_one("#composer", Input)

    def theme_color(self, name: str, fallback: str) -> str:
        return self.get_css_variables().get(name, fallback)

    def action_close_panel(self) -> None:
        if self.panel is not None:
            picker.close_panel(self)
            self.composer.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "composer":
            dispatch.on_input_changed(self, event.value)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "composer":
            await dispatch.on_input_submitted(self, event.value)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        await dispatch.on_option_selected(self, event)


if __name__ == "__main__":
    SymposeCLI().run()
