"""The Textual app shell: a persistent, always-live `Input` docked at the
bottom with a scrolling transcript above it — the one thing legacy's
blocking `rich.prompt.Prompt` loop couldn't do (see `docs/VISION.md`,
lines 46-50). Chat replies now come from the real engine
(`sympose/engine/`, docs/decisions/006); model/persona pickers use real
data (`mock_data.py`); `/compact`, `/settings`, and `/history` are still
inert or mock, since nothing backs them yet. Event handling and the
actual command/streaming behavior live in `dispatch.py`/`runtime.py`/
`turns.py`/`picker.py`, split out to hold the 200-LOC-per-file cap."""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Input, OptionList, Static

from sympose.cli import dispatch, picker, turns
from sympose.cli import transcript as transcript_mod
from sympose.cli.composer import ComposerInput
from sympose.cli.mock_data import list_personas
from sympose.cli.selection import SelectionPanel
from sympose.profile import resolve_default_persona


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
        margin: 0 1 1 1;
    }
    #composer.composer-spaced {
        /* Full shorthand here too, not just `margin-top` — Textual's
        CSS doesn't merge a single longhand override from a more
        specific selector with the base rule's other three sides the
        way plain CSS cascading would; it resets them, so this must
        restate all four rather than just the one that actually
        differs. */
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
        if not personas:
            # list_profiles() now deliberately returns [] once a
            # profiles/ dir exists but has no valid <handle>/persona.yaml in it
            # (docs/decisions/009) -- `personas[0]` below would be a
            # cryptic IndexError instead of an actionable message.
            raise RuntimeError(
                "No personas configured -- check SYMPOSE_PROFILES_DIR points "
                "at a directory containing at least one <handle>/persona.yaml."
            )
        # The configured default persona (factory default: Samantha, see
        # `CLAUDE.md`'s project rules) — picked explicitly rather than
        # whichever profile happens to sort first alphabetically.
        default_handle = resolve_default_persona()
        self.persona = next(
            (p for p in personas if p.handle == default_handle), personas[0]
        )
        # `None` until `/model` picks one, so a persona's own model (or the
        # `chat_model` setting) applies — see `mock_data.active_model`.
        self.model_override = None
        self.panel: SelectionPanel | None = None
        self.panel_kind: str | None = None
        # One session per CLI process run — the engine starts a new one on
        # the first real turn; `/clear` wipes the visible transcript only,
        # it does not reset this (no `/new`-style command exists yet).
        self.session_id: str | None = None
        # Bumped every time `session_id` is deliberately reset (a persona
        # switch). A call still in flight when that happens must not write
        # its own (now-stale) session_id back once it resolves — comparing
        # against the persona handle alone isn't enough, since switching
        # away and back to the *same* persona before the call resolves
        # would restore a matching handle with a stale session_id anyway;
        # this counter catches that too, not just a switch to someone else.
        self.session_generation = 0
        # The session id each generation actually resolved to, so a queued
        # message for the same persona/generation can continue it even if
        # an unrelated persona switch has since reset `session_id` itself
        # (docs/decisions/008). `session_id` above stays a convenient
        # mirror of the *current* generation's entry here.
        self.session_by_generation: dict[int, str | None] = {}
        # One lock per persona handle (docs/decisions/008), not a single
        # global one: sessions are stored per-handle
        # (sympose/engine/session.py), so two different personas' turns
        # never touch the same file and never actually race each other —
        # only two turns for the *same* persona need to queue behind one
        # another. The composer itself is never blocked either way.
        self.turn_locks: dict[str, asyncio.Lock] = {}
        # Every currently-streaming reply's own timer — not a single slot,
        # since turns for different personas (or two queued same-persona
        # turns) can now genuinely stream concurrently post-lock.
        self.active_reply_timers: set = set()
        # A plain counter, not `turn_locks[...].locked()`, for "is any turn
        # genuinely in flight right now" (docs/decisions/008): incremented
        # the instant `send_message` starts and decremented only once it's
        # fully done, covering the *whole* call including any time spent
        # queued. `Lock.locked()` is a point-in-time snapshot that briefly
        # reads `False` in the gap between one queued call releasing the
        # lock and the next one resuming to re-acquire it — a real, if
        # narrow, window where `/quit` could wrongly take the graceful
        # path and reproduce the exact hang this mechanism exists to
        # prevent (an already-running blocking call can't be cancelled).
        self.pending_turns = 0
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
            self, "Talking to the real engine now — local by default.", "system"
        )
        transcript_mod.mount_line(self, "Type a message, or / for commands.", "system")
        picker.close_panel(self)  # syncs the composer's initial spacing (no panel yet)
        self.composer.focus()

    async def action_quit(self) -> None:
        # Textual's default ctrl+q binding and command-palette "Quit" both
        # call this directly, bypassing `/quit`'s own in-flight check
        # (`sympose/cli/turns.py`) entirely — reintroducing the exact hang
        # that check exists to prevent, just through a different exit
        # route. Overriding here, rather than only guarding the `/quit`
        # command, covers every way this app can be told to quit.
        # `pending_turns`, not `turn_locks[...].locked()` — any persona's
        # turn counts, in flight *or* still queued behind another.
        if self.pending_turns > 0:
            turns._force_exit()
            return
        self.exit()

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
