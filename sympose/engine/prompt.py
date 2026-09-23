"""System-prompt assembly for a turn: persona identity, grounding evidence,
and the zero-hallucination instruction (docs/decisions/006). `PLACEHOLDER_SOUL`
is a minimal stand-in for Samantha's real voice-from-*Her* content, which is
its own later, separately-scoped piece of product writing, not engine work."""

from typing import Any

PLACEHOLDER_SOUL = (
    "You are a warm, direct conversational companion talking with the user "
    "about their Obsidian vault. Keep replies natural and concise."
)

_GROUNDING_INSTRUCTION = (
    "Only state facts about the user's vault that are backed by the vault "
    "context above. If nothing above answers the question, say so rather "
    "than guessing."
)


def _format_grounding_block(grounding_results: list[dict[str, Any]]) -> str:
    if not grounding_results:
        return "No vault notes matched this message."
    lines = ["Vault context:"]
    for result in grounding_results:
        lines.append(f"- {result['title']} ({result['rel_path']}): {result['snippet']}")
    return "\n".join(lines)


def build_system_prompt(profile: dict[str, Any], grounding_results: list[dict[str, Any]]) -> str:
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
    return "\n\n".join(
        [
            PLACEHOLDER_SOUL,
            identity,
            _format_grounding_block(grounding_results),
            _GROUNDING_INSTRUCTION,
        ]
    )


def build_messages(
    profile: dict[str, Any],
    history: list[dict[str, str]],
    grounding_results: list[dict[str, Any]],
    user_message: str,
) -> list[dict[str, str]]:
    system = {"role": "system", "content": build_system_prompt(profile, grounding_results)}
    user = {"role": "user", "content": user_message}
    return [system, *history, user]
