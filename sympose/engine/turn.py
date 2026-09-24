"""One turn, end to end (docs/decisions/006). `run_turn` stays a single
atomic unit (ground -> build -> call -> persist) — message queueing
(docs/decisions/008) is implemented at the CLI call site, sequencing and
attributing `run_turn` calls per persona, not inside this function.
`call_model` is a single blocking, non-cancelable call (ADR 007); there is
no in-progress generation to check for new input against, so the seam this
docstring used to point at (between the model call returning and the turn
persisting) was never exercised — see ADR 008."""

from dataclasses import dataclass, field
from typing import Any

from sympose import profile as profile_mod
from sympose.engine import budget, followup, prompt, session
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError

__all__ = ["TurnResult", "run_turn", "EngineModelError", "PersonaNotFoundError"]


class PersonaNotFoundError(Exception):
    """`resolve_profile(handle)` returned `None` — defensive-only today
    (the CLI's persona picker only ever offers real roster handles), but
    must degrade to a legible error instead of crashing a few lines
    further into `run_turn` on a bare `None`."""


@dataclass(frozen=True)
class TurnResult:
    reply: str
    session_id: str
    grounding: list[dict[str, Any]] = field(default_factory=list)
    # Time to first token in ms and the model that produced it
    # (docs/decisions/013); `None` when a caller builds a result by hand.
    ttft_ms: int | None = None
    model: str | None = None
    # Turns left out of what the model was sent because they did not fit its
    # window (docs/decisions/015); the session record keeps them all.
    history_dropped: int = 0
    # The search query a follow-up was rewritten into when that rewrite is what
    # grounded the reply (docs/decisions/017); `None` when the message itself was.
    searched: str | None = None
    # The conversation's size as the next turn starts from it, and the prompt
    # budget it is measured against (docs/decisions/018); `None` when the
    # model's window is unknown.
    context_used: int | None = None
    context_limit: int | None = None
    # The reply stopped at the reply limit, so it may end mid-sentence.
    truncated: bool = False


def _reply_tokens(text: str, model: str) -> int:
    return budget.count_tokens([{"role": "assistant", "content": text}], model)


def run_turn(
    handle: str,
    user_message: str,
    session_id: str | None = None,
    model: str | None = None,
) -> TurnResult:
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        raise PersonaNotFoundError(f"No profile found for persona '{handle}'.")
    sid = session_id or session.new_session_id()
    # A brand-new sid resolves to a file that doesn't exist yet, so this is
    # a cheap `os.path.exists` check in that case, not a real extra read —
    # loading unconditionally lets the already-loaded state be handed
    # straight to `append_turn` below instead of it re-reading the file.
    existing = session.load_session(handle, sid)
    history = session.history_as_messages(existing)

    # An explicit per-call model wins; otherwise `resolve_model` owns the
    # rest of the order (persona's model > setting > default), so this
    # and every display of "which model runs" share one definition.
    target_model = model or model_mod.resolve_model(persona.get("model"))
    # The prompt is sized to this model's window, not left to the runtime's
    # silent cut (docs/decisions/015); the follow-up rewrite shares that window.
    limits = budget.budget_for(target_model)
    grounding_results, searched = followup.ground(persona, user_message, history, target_model, limits)

    found = len(grounding_results)

    def build(hist: list[dict[str, str]], hits: list[dict[str, Any]]) -> list[dict[str, str]]:
        # `found - len(hits)` passages were left out for size: the prompt says so
        # instead of claiming nothing matched.
        return prompt.build_messages(persona, hist, hits, user_message, omitted=found - len(hits))

    prompt_tokens = 0
    if limits is None:
        messages, dropped = build(history, grounding_results), 0
    else:
        fitted = budget.fit(build, history, grounding_results, target_model, limits.prompt_tokens)
        messages, grounding_results, dropped = fitted.messages, fitted.grounding, fitted.history_dropped
        prompt_tokens = fitted.tokens
    reply = model_mod.call_model(
        messages,
        model=target_model,
        num_ctx=limits.num_ctx if limits else None,
        max_tokens=limits.reply_cap if limits else None,
    )

    session.append_turn(
        handle,
        sid,
        user_message,
        reply.text,
        existing=existing,
        ttft_ms=reply.ttft_ms,
        model=target_model,
    )
    return TurnResult(
        reply=reply.text,
        session_id=sid,
        grounding=grounding_results,
        ttft_ms=reply.ttft_ms,
        model=target_model,
        history_dropped=dropped,
        searched=searched if grounding_results else None,
        context_used=prompt_tokens + _reply_tokens(reply.text, target_model) if limits else None,
        context_limit=limits.prompt_tokens if limits else None,
        truncated=reply.truncated,
    )
