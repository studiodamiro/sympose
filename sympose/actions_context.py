"""
`_ActionContext` (ADR-137, split out of actions.py) — the per-call state
every `_handle_*` tag handler needs. Its own tiny module so every handler
mixin (`actions_notes.py`, `actions_sub_agent.py`, `actions_persona.py`,
`actions_misc.py`) can import it for type hints without importing
`actions.py` itself, which would cycle (`actions.py` assembles
`ActionProcessor` from those same mixins).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _ActionContext:
    """The per-call state every `_handle_*` tag handler needs, bundled so
    `execute_actions`'s dispatch loop can call any of them uniformly as
    `handler(ctx, inner)` regardless of what that particular tag actually
    reads or writes. `badges` is the same list object `execute_actions`
    returns — handlers append to it directly rather than returning their
    own list, since `SPAWN_SUB_AGENT` needs to de-duplicate a recursive
    call's badges against everything accumulated in this call so far."""

    profile_manager: Any
    handle: str
    profile: dict
    name: str
    vault_folder: str
    is_shared: bool
    is_sub_agent: bool
    user_prompt: str
    depth: int
    on_progress: Callable[[str], None] | None
    # ADR-130: fired once per completed action alongside its badge, with a
    # structured {"action": <TAG_NAME>, "detail": <str>} the dashboard's
    # streaming chat endpoint forwards as a distinct SSE event (the badge
    # string itself stays terminal/Slack's own rendering, unchanged).
    # None (every caller before ADR-130) means zero behavior change.
    on_action: Callable[[dict[str, str]], None] | None = None
    badges: list[str] = field(default_factory=list)

    def fire_action(self, action: str, detail: str) -> None:
        """No-op when `on_action` is unset (every caller before ADR-130)."""
        if self.on_action:
            self.on_action({"action": action, "detail": detail})
