"""Mounts a line into the transcript with speaker-aware spacing.

The gap is a chat-message thing, not a general transcript thing: it
appears only between a "user" turn and a "persona" turn (or back), never
around "system" lines — hints, `/help` output, confirmations, errors.
Those always stay tight against whatever surrounds them, so a menu-like
block never picks up the chat's own breathing room."""

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

_CHAT_SPEAKERS = {"user", "persona"}


def styled_line(prefix: str, prefix_style: Style, body: str) -> Text:
    """A `rich.text.Text` built from a styled prefix followed by a plain
    body — the shape shared by the "You" line, a streamed reply's colored
    header, and `/help`'s colored command names."""
    text = Text()
    text.append(prefix, style=prefix_style)
    text.append(body)
    return text


def mount_line(app, content, speaker: str) -> Static:
    changed = (
        speaker in _CHAT_SPEAKERS
        and app.last_speaker in _CHAT_SPEAKERS
        and speaker != app.last_speaker
    )
    widget = Static(content, classes="turn-gap" if changed else "")
    app.transcript.mount(widget)
    app.last_speaker = speaker
    return widget
