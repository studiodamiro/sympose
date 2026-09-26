"""How the model's prompt is laid out (docs/decisions/020); the text itself, all of
it, is `prompt_text`, re-exported here so `prompt` is the one place to look. A small
model follows what sits last and nearest the question over what came first, so the
layout is:

    system:  the persona's soul, its name, how Sympose works, the rules
    history: the conversation so far
    user:    the notes found for this message, then the message

The notes travel with the question, not in the system prompt, where the soul's
own instructions ("ask a real question", "have a point of view") outweighed
them and the model chatted instead of answering from the notes (docs/decisions/019
and 020). The engine's rules stay after the soul, so no soul can weaken them
(docs/decisions/012)."""

from typing import Any

from sympose.engine.prompt_text import (
    ANSWER_FROM_NOTES, ANSWER_FROM_RECAPS, ANSWER_FROM_REFERENCE, DEFAULT_SOUL, GROUNDING_RULE,
    HOW_YOU_WORK, NO_NOTES, NO_RECAP, NO_REFERENCE, NO_TOPIC, POINT_TO_REFERENCE, RECAPS_LABEL,
    RECAP_INSTRUCTIONS, REFERENCE_LABEL, REWRITE_INSTRUCTIONS, SYMPOSE_RULE,
    EMPTY_NOTE, EMPTY_NOTE_ALIASES, EMPTY_NOTE_HEADINGS,
)
from sympose.persona_files import load_soul
from sympose.profile import reference_persona_names

__all__ = [
    "ANSWER_FROM_NOTES", "ANSWER_FROM_RECAPS", "ANSWER_FROM_REFERENCE", "DEFAULT_SOUL",
    "GROUNDING_RULE", "HOW_YOU_WORK", "NO_NOTES", "NO_RECAP", "NO_REFERENCE", "NO_TOPIC",
    "POINT_TO_REFERENCE", "RECAPS_LABEL", "RECAP_INSTRUCTIONS", "REFERENCE_LABEL",
    "REWRITE_INSTRUCTIONS", "SYMPOSE_RULE", "build_messages", "build_system_prompt",
    "build_user_turn",
]

# -- the layout --


def _reference_block(hits: list[dict[str, Any]], omitted: int = 0) -> str:
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


def _recaps_block(recaps: list[dict[str, Any]], omitted: int = 0) -> str | None:
    """The recaps of earlier conversations (given newest first), or a line saying some were left out to
    fit the window (so she does not claim there were none), or nothing at all."""
    if not recaps:
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


def _notes_block(grounding_results: list[dict[str, Any]], omitted: int = 0) -> str:
    """`omitted` is how many matching passages were left out to fit the
    model's window (docs/decisions/015): the block must say so, since "no
    notes matched" would be false and the model would tell the user the vault
    has nothing on it."""
    if not grounding_results:
        if omitted:
            return (
                "Notes in the vault matched this message, but they could not be included because "
                "the conversation is too long for the context window. Don't say the vault "
                "has nothing on it: say you couldn't include the matching notes this time."
            )
        return NO_NOTES
    lines = ["Notes found in the vault for this message:"]
    for result in grounding_results:
        heading = result.get("heading")
        where = result["rel_path"]
        if heading and heading != result["title"]:
            where += f" › {heading}"
        lines.append(f"- {result['title']} ({where}): {_text_of(result)}")
    if omitted:
        lines.append(f"({omitted} more matching passages were left out to fit the context window.)")
    return "\n".join(lines)


def build_system_prompt(
    profile: dict[str, Any], recaps: list[dict[str, Any]] | None = None, recaps_omitted: int = 0
) -> str:
    # `handle` is always lowercase (`profile.get_profile` lowercases it
    # before building a file path) -- title-cased here so a fallback
    # profile's identity line reads "Samantha", not "samantha". The
    # `or "Sam"` (not a `.get(..., "Sam")` default) matters: a profile
    # with an explicit `handle: null`/blank YAML value has the key
    # present but falsy, and `.get(key, default)`'s default only ever
    # applies when the key is *absent* -- a `.get("handle", "Sam")`
    # default here would silently return `None` and crash on `.title()`.
    name = profile.get("name") or (profile.get("handle") or "Sam").title()
    soul = load_soul(profile["handle"]) if profile.get("handle") else None
    aliases = [a for a in profile.get("aliases") or [] if isinstance(a, str) and a.strip()]
    identity = f"Your name is {name}." + (f" The user may also call you {' or '.join(aliases)}." if aliases else "")
    parts = [soul or DEFAULT_SOUL, identity, HOW_YOU_WORK, GROUNDING_RULE]
    if profile.get("sympose_reference"):
        parts.append(SYMPOSE_RULE)
    # Recaps go here, not in the message: beside a request in the middle of a chat that is on the
    # same topic as a recap, they made her comment on the conversation instead of continuing it
    # (docs/decisions/026).
    recaps_block = _recaps_block(recaps or [], recaps_omitted)
    if recaps_block:
        parts.append(recaps_block)
    return "\n\n".join(parts)


def build_user_turn(
    user_message: str,
    grounding_results: list[dict[str, Any]],
    omitted: int = 0,
    reference: bool = False,
    reference_omitted: int = 0,
    point_to: list[str] | None = None,
) -> str:
    """`reference`: the persona has the Sympose reference library, so the turn
    says what it found in it (or that nothing matched). Its passages are marked
    `source: "sympose"` and kept apart from the user's own notes; `omitted` and
    `reference_omitted` count the passages of each left out for size. `point_to`:
    the personas that have the library, for one that does not to send the user to."""
    reference_hits = [h for h in grounding_results if h.get("source") == "sympose"]
    notes = [h for h in grounding_results if h.get("source") != "sympose"]
    parts = [_notes_block(notes, omitted)]
    if notes:
        parts.append(ANSWER_FROM_NOTES)
    if reference:
        parts.append(_reference_block(reference_hits, reference_omitted))
        if reference_hits:
            parts.append(ANSWER_FROM_REFERENCE)
    if point_to and not reference:
        parts.append(POINT_TO_REFERENCE.format(names=" or ".join(point_to)))
    parts.append(f"User's message: {user_message}")
    return "\n\n".join(parts)


def build_messages(
    profile: dict[str, Any],
    history: list[dict[str, str]],
    grounding_results: list[dict[str, Any]],
    user_message: str,
    omitted: int = 0,
    reference_omitted: int = 0,
    point_to: list[str] | None = None,
    recaps: list[dict[str, Any]] | None = None,
    recaps_omitted: int = 0,
) -> list[dict[str, str]]:
    """The system prompt (with the recaps of earlier conversations, docs/decisions/023 and 026),
    the history as it was said (the notes of earlier turns are not repeated), and this turn's
    notes with the message. `point_to`: the
    personas that have the reference library, read from the roster when not given
    (a turn gives it once, since fitting builds this many times)."""
    system = {"role": "system", "content": build_system_prompt(profile, recaps, recaps_omitted)}
    has_library = bool(profile.get("sympose_reference"))
    if point_to is None:
        point_to = [] if has_library else reference_persona_names()
    user = {
        "role": "user",
        "content": build_user_turn(
            user_message, grounding_results, omitted, has_library, reference_omitted, point_to
        ),
    }
    return [system, *history, user]
