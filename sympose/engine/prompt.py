"""System-prompt assembly for a turn: the persona's soul (voice only,
docs/decisions/012), its identity, grounding evidence, and the
zero-hallucination instruction (docs/decisions/006). The grounding
instruction is appended last and lives here, not in any soul, so every
persona gets it and no soul can weaken it."""

from typing import Any

from sympose.profile import load_soul

# The fallback for a persona with no `soul.md` — generic on purpose.
DEFAULT_SOUL = (
    "You are a warm, direct conversational companion talking with the user "
    "about their Obsidian vault. Keep replies natural and concise."
)

_GROUNDING_INSTRUCTION = (
    "Only state facts about the user's vault that are backed by the vault "
    "context above. If nothing above answers the question, say you couldn't "
    "find it in the vault rather than guessing. Don't claim to know things "
    "about the user that aren't in this conversation or the vault context "
    "above, and if they refer to something you can't see (\"that layout\", "
    "\"this note\"), ask what they mean instead of assuming."
)

# What this engine can't do yet, stated to every persona so a warm voice
# never plays along with an action that won't happen. Drop or narrow this
# as tool-calling (MCP) lands — see docs/decisions/012.
_CAPABILITY_LIMITS = (
    "You can read the vault context above and talk with the user, but you "
    "can't create or change notes, personas, or settings, or run tools. If "
    "asked to, say so plainly instead of pretending."
)


def _format_grounding_block(grounding_results: list[dict[str, Any]], omitted: int = 0) -> str:
    """`omitted` is how many matching passages were left out to fit the
    model's window (docs/decisions/015): the block must say so, since "no
    notes matched" would be false and the model would tell the user the vault
    has nothing on it."""
    if not grounding_results:
        if omitted:
            return (
                "Vault notes matched this message, but they could not be included because "
                "the conversation is too long for the context window. Don't say the vault "
                "has nothing on it: say you couldn't include the matching notes this time."
            )
        return "No vault notes matched this message."
    lines = ["Vault context:"]
    for result in grounding_results:
        heading = result.get("heading")
        where = result["rel_path"]
        if heading and heading != result["title"]:
            where += f" › {heading}"
        lines.append(f"- {result['title']} ({where}): {result['text']}")
    if omitted:
        lines.append(f"({omitted} more matching passages were left out to fit the context window.)")
    return "\n".join(lines)


def build_system_prompt(
    profile: dict[str, Any], grounding_results: list[dict[str, Any]], omitted: int = 0
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
    identity = f"Your name is {name}."
    soul = load_soul(profile["handle"]) if profile.get("handle") else None
    return "\n\n".join(
        [
            soul or DEFAULT_SOUL,
            identity,
            _format_grounding_block(grounding_results, omitted),
            _GROUNDING_INSTRUCTION,
            _CAPABILITY_LIMITS,
        ]
    )


def build_messages(
    profile: dict[str, Any],
    history: list[dict[str, str]],
    grounding_results: list[dict[str, Any]],
    user_message: str,
    omitted: int = 0,
) -> list[dict[str, str]]:
    system = {"role": "system", "content": build_system_prompt(profile, grounding_results, omitted)}
    user = {"role": "user", "content": user_message}
    return [system, *history, user]
