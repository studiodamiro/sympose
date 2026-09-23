"""The reply header's grounded-notes segment (docs/decisions/016): which note
a reply was grounded on, fitted to the terminal's width, and nothing at all
when nothing matched. Split out of `turns.py` to hold the 200-LOC-per-file cap."""

from typing import Any

from rich.cells import cell_len

from sympose import settings_store

SETTING = "show_grounding"

_ELLIPSIS = "…"
# In a very narrow terminal the header runs over instead: a cut path that
# loses its filename says nothing. The floor is the whole filename plus the
# ellipsis, but never more than this, so one huge filename cannot take the line.
_MIN_PATH_WIDTH = 8
_MAX_KEPT_FILENAME = 32
# Cells the transcript keeps for its own padding and scrollbar.
_MARGIN = 4


def enabled() -> bool:
    """On unless explicitly turned off: a hand-edited or malformed value
    (`"false"`, `0`) must not silently hide what grounded a reply."""
    return settings_store.flag(SETTING)


def set_enabled(value: bool) -> bool:
    return settings_store.set(SETTING, value)


def _fit_from_front(path: str, width: int) -> str:
    """`path` whole if it fits `width` terminal cells, else its tail behind
    an ellipsis, so the filename, the part that identifies the note, stays
    visible. Measured in cells, not characters: a CJK or emoji filename takes
    two cells per character."""
    if cell_len(path) <= width:
        return path
    kept: list[str] = []
    used = cell_len(_ELLIPSIS)
    for char in reversed(path):
        used += cell_len(char)
        if used > width:
            break
        kept.append(char)
    return _ELLIPSIS + "".join(reversed(kept))


def format_grounding(hits: list[dict[str, Any]], room: int) -> str:
    """The segment for a header with `room` cells left on its line:
    `from <top note> +N`, or `""` when nothing matched: a message that was
    never about a note would otherwise read as a claim about the vault. A hit
    without a path is skipped, since this is display only and must never cost
    the user a reply that exists."""
    paths = list(dict.fromkeys(hit["rel_path"] for hit in hits if hit.get("rel_path")))
    if not paths:
        return ""
    suffix = f" +{len(paths) - 1}" if len(paths) > 1 else ""
    label = "from "
    filename_width = cell_len(paths[0].rsplit("/", 1)[-1]) + cell_len(_ELLIPSIS)
    floor = max(_MIN_PATH_WIDTH, min(filename_width, _MAX_KEPT_FILENAME))
    width = max(room - len(label) - len(suffix), floor)
    return f"{label}{_fit_from_front(paths[0], width)}{suffix}"


def header_segment(header: str, hits: list[dict[str, Any]], terminal_width: int) -> str:
    """` · <segment>` to append to `header`, or `""` when the knob is off or
    nothing matched."""
    if not enabled():
        return ""
    separator = " · "
    room = terminal_width - cell_len(header) - len(separator) - _MARGIN
    segment = format_grounding(hits, room)
    return separator + segment if segment else ""
