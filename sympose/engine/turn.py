"""One turn, end to end (docs/decisions/006). Each step below is a
separately callable function rather than inlined logic, specifically so the
seam between the model call returning (step 7) and persisting/returning
(step 8) is visible — that's where a later message-queueing milestone would
check for newly-arrived input before finalizing a turn. Queueing itself is
not implemented here."""

from dataclasses import dataclass, field
from typing import Any

from sympose import profile as profile_mod
from sympose.engine import grounding, prompt, session
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError

__all__ = ["TurnResult", "run_turn", "EngineModelError"]


@dataclass(frozen=True)
class TurnResult:
    reply: str
    session_id: str
    grounding: list[dict[str, Any]] = field(default_factory=list)


def run_turn(
    handle: str,
    user_message: str,
    session_id: str | None = None,
    model: str | None = None,
) -> TurnResult:
    persona = profile_mod.resolve_profile(handle)
    sid = session_id or session.new_session_id()
    # A brand-new sid resolves to a file that doesn't exist yet, so this is
    # a cheap `os.path.exists` check in that case, not a real extra read —
    # loading unconditionally lets the already-loaded state be handed
    # straight to `append_turn` below instead of it re-reading the file.
    existing = session.load_session(handle, sid)
    history = session.history_as_messages(existing)

    grounding_results = grounding.ground(persona, user_message)
    messages = prompt.build_messages(persona, history, grounding_results, user_message)
    reply = model_mod.call_model(messages, model=model)

    session.append_turn(handle, sid, user_message, reply, existing=existing)
    return TurnResult(reply=reply, session_id=sid, grounding=grounding_results)
