"""The context meter (docs/decisions/018): one dim line under the chat box,
`context ██████░░░░ 62%`, saying how much of the prompt budget the
conversation uses. At 100% the next turn starts leaving older turns out."""

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from sympose import settings_store

SETTING = "show_context_meter"

_BAR_CELLS = 10
_WARN_AT = 70
_ERROR_AT = 90


class ContextMeter(Static):
    """Empty until a reply has been counted. Sits in the line the composer's
    own bottom margin used to leave free, so the screen does not grow."""

    # Bumped whenever the meter is reset (a model or persona switch), so a
    # reply that was already in flight when that happened can tell it is stale.
    epoch = 0

    DEFAULT_CSS = """
    ContextMeter {
        height: 1;
        margin: 0 2 0 2;
        color: $text-muted;
    }
    """


def enabled() -> bool:
    """On unless explicitly turned off, like the other display knobs."""
    return settings_store.flag(SETTING)


def percent(used: int, limit: int) -> int:
    """Whole percent of `limit` in use, never above 100: once turns are being
    left out the header's notice says how many. 100 means the budget is
    reached, so a hair under it reads 99."""
    pct = min(100, max(0, round(used * 100 / limit)))
    return pct if used >= limit else min(pct, 99)


def format_meter(used: int, limit: int, warn: str, error: str) -> Text:
    pct = percent(used, limit)
    filled = round(pct * _BAR_CELLS / 100)
    text = Text(f"context {'█' * filled}{'░' * (_BAR_CELLS - filled)} {pct}%")
    if pct >= _ERROR_AT:
        text.stylize(Style(color=error))
    elif pct >= _WARN_AT:
        text.stylize(Style(color=warn))
    return text


def epoch(app) -> int:
    return app.query_one(ContextMeter).epoch


def clear(app) -> None:
    """Empties the line and makes any reply still in flight stale."""
    widget = app.query_one(ContextMeter)
    widget.epoch += 1
    widget.update("")


def show(app, used: int | None, limit: int | None, since: int) -> None:
    """Shows the conversation's size after a reply that was sent when the
    meter's epoch was `since`; a reply that has since been made stale by a
    reset is ignored. A missing figure (the model's window is unknown) or the
    knob being off leaves the line empty."""
    widget = app.query_one(ContextMeter)
    if widget.epoch != since:
        return
    if used is None or not limit or not enabled():
        widget.update("")
        return
    warn, error = app.theme_color("warning", "yellow"), app.theme_color("error", "red")
    widget.update(format_meter(used, limit, warn, error))
