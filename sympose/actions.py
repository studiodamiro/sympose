"""
Autonomic Action Tag Processor for Sympose Personas.

`execute_actions` used to be one function with a 14-branch if/elif chain
over tag names, each branch's full body inlined — mccabe flagged it at
complexity 66. Restructured the same way as `commands.py`'s `intercept`
(ADR-125 follow-up): each tag's body moved into its own `_handle_*`
method, dispatched through a small (gate, handler) table keyed by tag
name (`_tag_routes`) so `execute_actions` itself is just the tag loop
plus one table lookup, not 14 sequential `elif` branches.

ADR-137: this used to be one ~810-line module; the handlers themselves
now live in focused mixins (`actions_parsing.py`, `actions_notes.py`,
`actions_sub_agent.py`, `actions_persona.py`, `actions_misc.py`), the
same "thin core assembling mixins" pattern ADR-125 already established
for `PersonaEngine`/`VaultManager`. `TAG_NAMES`/`_PSEUDO_TAG_RE` stay
here rather than in a mixin: `_PSEUDO_TAG_RE`'s own construction embeds
`TAG_NAMES` via `"|".join(TAG_NAMES)` at class-body-execution time, which
only resolves against names already in *this* class body's own local
namespace — inheritance doesn't help there, only inside method bodies
(where `cls.TAG_NAMES` works fine, e.g. `_consume_tag_at`). Every handler
shares its call's context (profile, name, badges list, …) through
`_ActionContext` (its own tiny module, `actions_context.py`, so every
mixin can type-hint it without importing this file and cycling back)
instead of closing over engine-turn locals, since — unlike `commands.py`'s
per-command handlers — several of these run recursively
(`SPAWN_SUB_AGENT` re-invokes `execute_actions` on sub-agent output).
"""

import re
from collections.abc import Callable
from typing import Any, ClassVar

from sympose.actions_context import _ActionContext
from sympose.actions_misc import MiscActionMixin
from sympose.actions_notes import NotesActionMixin
from sympose.actions_parsing import ParsingMixin
from sympose.actions_persona import PersonaActionMixin
from sympose.actions_sub_agent import SubAgentActionMixin

# Re-exported for the test suite: several tests monkeypatch a method on one
# of these (e.g. "sympose.actions.VaultManager.write_note") rather than a
# top-level name — since that mutates the shared class/singleton object
# itself, patching it via this import path or a mixin's own import of the
# same object has an identical effect. Not used directly anywhere in this
# file's own code below; keep these imports if a future cleanup pass is
# tempted to remove them as "unused".
from sympose.config import config_manager  # noqa: F401
from sympose.native_tools import NativeTools  # noqa: F401
from sympose.sub_agents import SubAgentEngine, SubAgentTask  # noqa: F401
from sympose.vault import VaultManager  # noqa: F401

__all__ = ["ActionProcessor"]


class ActionProcessor(
    ParsingMixin,
    NotesActionMixin,
    SubAgentActionMixin,
    PersonaActionMixin,
    MiscActionMixin,
):
    """Parses, executes, and badges autonomic model action tags ([REMEMBER], [WRITE_NOTE], [DAILY_NOTE], [CONFIG_SET], etc.)."""

    TAG_NAMES: ClassVar[list[str]] = [
        "DAILY_NOTE",
        "WRITE_NOTE",
        "APPEND_NOTE",
        "REMEMBER",
        "READ_NOTE",
        "VIEW_NOTE",
        "SPAWN_SUB_AGENT",
        "SEARCH",
        "WEB_SEARCH",
        "CONFIG_SET",
        "CREATE_PERSONA",
        "DELETE_PERSONA",
        "WRITE_CANVAS",
        "REACT",
    ]

    # SPAWN_SUB_AGENT re-invokes execute_actions on sub-agent output; caps that
    # chain so a sub-agent synthesis containing another [SPAWN_SUB_AGENT: ...]
    # can't recurse unboundedly.
    MAX_ACTION_DEPTH = 1

    # Retired tag names from before the Worker -> Sub-Agent rename. An
    # unrecognized tag name isn't caught by any malformed-tag fallback — it
    # just silently prints as inert literal text instead of running (seen in
    # practice from weaker/local models reverting to the old spelling). This
    # catches the known case and turns it into a visible warning instead of a
    # silent no-op.
    _LEGACY_TAG_RE = re.compile(r"\[(?:ACTION:)?SPAWN_WORKER:[^\]]*\]", re.IGNORECASE)

    # A model can invent its own bracket notation that merely *looks* like
    # our tag syntax (e.g. `[GAME_STATE_UPDATE]`, seen live from a local
    # model narrating a roleplay game) - unlike a mistyped real tag, this
    # never matches any name in TAG_NAMES, so parse_action_tags never sees
    # it and it just prints as raw literal text. Caught by shape (an
    # all-caps, underscored identifier alone in brackets - the same
    # structural pattern every real tag name follows) rather than by
    # enumerating every name a model might dream up; real tag names are
    # excluded so an already-handled tag's own bracket is never touched
    # here even if something upstream left it unprocessed.
    _PSEUDO_TAG_RE = re.compile(
        r"\[(?:ACTION:)?(?!(?:" + "|".join(TAG_NAMES) + r")\b)"
        r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?::[^\]]*)?\]"
    )

    @classmethod
    def _tag_routes(
        cls,
    ) -> dict[str, tuple[Callable[[str], bool], Callable[["_ActionContext", str], str]]]:
        """(gate, handler) per tag name. Handlers return the text (if any)
        to append to `clean_text`; badges are appended to `ctx.badges`
        directly by the handler itself. READ_NOTE/VIEW_NOTE and
        SEARCH/WEB_SEARCH are pairs of tag spellings sharing one handler."""
        return {
            "WRITE_NOTE": (cls._has_pipe, cls._handle_write_note),
            "APPEND_NOTE": (cls._has_pipe, cls._handle_append_note),
            "DAILY_NOTE": (cls._non_empty, cls._handle_daily_note),
            "REMEMBER": (cls._non_empty, cls._handle_remember),
            "READ_NOTE": (cls._non_empty_stripped, cls._handle_read_note),
            "VIEW_NOTE": (cls._non_empty_stripped, cls._handle_read_note),
            "SPAWN_SUB_AGENT": (cls._has_pipe, cls._handle_spawn_sub_agent),
            "SEARCH": (cls._non_empty_stripped, cls._handle_search),
            "WEB_SEARCH": (cls._non_empty_stripped, cls._handle_search),
            "CONFIG_SET": (cls._has_pipe, cls._handle_config_set),
            "CREATE_PERSONA": (cls._always_true, cls._handle_create_persona),
            "DELETE_PERSONA": (cls._non_empty, cls._handle_delete_persona),
            "WRITE_CANVAS": (cls._has_pipe, cls._handle_write_canvas),
        }

    @classmethod
    def execute_actions(
        cls,
        profile_manager: Any,
        handle: str,
        text: str,
        user_prompt: str = "",
        depth: int = 0,
        on_progress: Callable[[str], None] | None = None,
        on_action: Callable[[dict[str, str]], None] | None = None,
    ) -> tuple[str, list[str]]:
        """Executes all detected action tags in model output and returns
        (clean_text, confirmation_badges). `on_progress`, if given, is passed
        straight through to a spawned sub-agent's tool-call loop so a caller
        can show live progress during what would otherwise be a silent,
        multi-turn synchronous wait — see SubAgentEngine.execute_sub_agent_task.
        `on_action`, if given (ADR-130), fires once per completed action tag
        with a structured `{"action": <TAG_NAME>, "detail": <str>}` — the
        dashboard's streaming chat endpoint uses this to emit a distinct SSE
        event per action; `None` (every caller before ADR-130) is a no-op."""
        is_sub_agent = handle.lower() == "sub_agent"
        profile = profile_manager.get_profile(handle) if not is_sub_agent else {}
        if not profile and not is_sub_agent:
            return text, []

        name = "Sub-Agent" if is_sub_agent else profile.get("name", handle)
        ctx = _ActionContext(
            profile_manager=profile_manager,
            handle=handle,
            profile=profile,
            name=name,
            vault_folder=profile.get("vault_folder", ""),
            is_shared=profile.get("share_memory", False),
            is_sub_agent=is_sub_agent,
            user_prompt=user_prompt,
            depth=depth,
            on_progress=on_progress,
            on_action=on_action,
        )
        badges = ctx.badges

        tags = cls.parse_action_tags(text)
        clean_text = text

        legacy_matches = cls._LEGACY_TAG_RE.findall(clean_text)
        if legacy_matches:
            clean_text = cls._LEGACY_TAG_RE.sub("", clean_text)
            badges.append(
                f"> ⚠️ **{name} used the retired `[SPAWN_WORKER]` tag — nothing "
                "was dispatched.** The current sub-agent tag is "
                "`[SPAWN_SUB_AGENT: ...]`."
            )

        routes = cls._tag_routes()
        # A model that repeats itself (common with weaker/local models) can
        # emit the exact same tag twice — the text strip below is already
        # idempotent, but without this guard the tag's real side effect
        # (writing/appending a note, spawning a sub-agent, remembering a fact)
        # would otherwise fire once per repeated occurrence.
        seen_raw_tags: set[str] = set()

        for tag, inner, raw_tag in tags:
            clean_text = clean_text.replace(raw_tag, "")
            if raw_tag in seen_raw_tags:
                continue
            seen_raw_tags.add(raw_tag)

            # REACT is handled upstream by slack.py, which regex-matches it
            # directly against the raw model output to drive emoji reactions
            # (see strip_action_tags). It reaches this loop as an already
            # recognized, already handled tag — no-op it here rather than
            # falling into the malformed-tag branch below.
            if tag == "REACT":
                continue

            route = routes.get(tag)
            if route and route[0](inner):
                clean_text += route[1](ctx, inner)
            elif tag in cls.TAG_NAMES:
                # ADR-071: a recognized tag whose shape didn't match its
                # handler's gate (e.g. `[WRITE_NOTE: filename]` with no
                # `|content`) previously did nothing silently — the model
                # had no signal its action didn't run, violating
                # ground-truth sovereignty (ADR-024: don't let the model
                # believe unverified state). Surface it instead of
                # swallowing it.
                badges.append(
                    f"> ⚠️ **Malformed `[{tag}]` action tag — ignored (missing or invalid arguments).**"
                )

        clean_text = cls._PSEUDO_TAG_RE.sub("", clean_text)
        clean_text = re.sub(r"```[a-zA-Z0-9_-]*\s*```\n?", "", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
        return clean_text, badges
