"""The blocks of a turn's prompt that say what was found (docs/decisions/020): the notes, the Sympose
reference and the recaps of earlier conversations, and what to say when some of it could not be
included (it did not fit the window, or the user has not allowed a cloud model to receive it,
docs/decisions/031). How they are laid out is `prompt`."""

from typing import Any

from sympose.engine.prompt_text import (
    ANSWER_FROM_RECAPS, EMPTY_NOTE, EMPTY_NOTE_ALIASES, EMPTY_NOTE_HEADINGS, NO_NOTES, NO_REFERENCE,
    RECAPS_LABEL, REFERENCE_LABEL, WITHHELD_NOTES, WITHHELD_PROPERTIES, WITHHELD_RECAPS,
)
from sympose.engine.sharing import NOTES, PROPERTIES


def reference_block(hits: list[dict[str, Any]], omitted: int = 0) -> str:
    """`omitted`: matching passages left out to fit the window, which must not
    be reported as "nothing matched" (docs/decisions/015)."""
    if not hits:
        if omitted:
            return (
                "Sympose reference passages matched this message, but they could not be included "
                "because the conversation is too long for the context window. Don't say Sympose "
                "does not do it: say you couldn't include the reference this time."
            )
        return NO_REFERENCE
    lines = [REFERENCE_LABEL]
    for hit in hits:
        where = hit["title"] if hit.get("heading") in (None, "", hit["title"]) else f"{hit['title']} › {hit['heading']}"
        lines.append(f"- {where}: {_text_of(hit)}")
    if omitted:
        lines.append(f"({omitted} more reference passages were left out to fit the context window.)")
    return "\n".join(lines)


def _text_of(result: dict[str, Any]) -> str:
    """What a grounded note says; a note with no text of its own is shown as empty, with its other names."""
    if result.get("kind") != "title":
        return result["text"]
    headings = result.get("heading") and result["heading"] != result["title"]  # as `where` shows them
    return (
        EMPTY_NOTE
        + (EMPTY_NOTE_HEADINGS if headings else "")
        + (EMPTY_NOTE_ALIASES.format(names=result["text"]) if result["text"] else "")
    )


def recaps_block(recaps: list[dict[str, Any]], omitted: int = 0, withheld: int = 0) -> str | None:
    """The recaps of earlier conversations (given newest first), or a line saying some were left out to
    fit the window or were not allowed to reach a cloud model (so she does not claim there were none),
    or nothing at all."""
    if not recaps:
        if withheld:
            return WITHHELD_RECAPS
        if omitted:
            return (
                "Recaps of earlier conversations exist but could not be included because the "
                "conversation is too long for the context window. Don't say there were none: "
                "say you couldn't include them this time."
            )
        return None
    # Named by whether it really is the last conversation, not left to the dates: a small
    # model has no idea what day it is, so "last time" would otherwise be any of them.
    # Oldest first, since it leans on what it read last, which must be the newest.
    lines = [RECAPS_LABEL] + [
        f"- {'Last conversation' if recap['last'] else 'An earlier conversation'} ({recap['date']}): {recap['text']}"
        for recap in reversed(recaps)
    ]
    if omitted:
        lines.append(f"({omitted} more recaps were left out to fit the context window.)")
    lines.append(ANSWER_FROM_RECAPS)
    return "\n".join(lines)


def notes_block(
    grounding_results: list[dict[str, Any]], omitted: int = 0, withheld: dict[str, int] | None = None
) -> str:
    """`omitted` is how many matching passages were left out to fit the
    model's window (docs/decisions/015): the block must say so, since "no
    notes matched" would be false and the model would tell the user the vault
    has nothing on it. `withheld` is what the user has not allowed a cloud
    model to receive (docs/decisions/031), which must be said for the same reason."""
    withheld = withheld or {}
    held = [text for category, text in ((NOTES, WITHHELD_NOTES), (PROPERTIES, WITHHELD_PROPERTIES)) if withheld.get(category)]
    if not grounding_results:
        # Every reason there is, since "the vault has nothing" would be false for each of them.
        reasons = held + (
            [
                "Notes in the vault matched this message, but they could not be included because "
                "the conversation is too long for the context window. Don't say the vault "
                "has nothing on it: say you couldn't include the matching notes this time."
            ]
            if omitted
            else []
        )
        return "\n".join(reasons) or NO_NOTES
    lines = ["Notes found in the vault for this message:"]
    for result in grounding_results:
        heading = result.get("heading")
        where = result["rel_path"]
        if heading and heading != result["title"]:
            where += f" › {heading}"
        lines.append(f"- {result['title']} ({where}): {_text_of(result)}")
    if omitted:
        lines.append(f"({omitted} more matching passages were left out to fit the context window.)")
    lines.extend(held)
    return "\n".join(lines)
