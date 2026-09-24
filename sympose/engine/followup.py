"""Follow-up-aware grounding (docs/decisions/017): a message such as "why did
we pick it?" has no searchable words, so nothing is grounded even though the
notes were found a turn earlier. The message is searched as usual first; only
when that finds nothing and the chat has earlier turns, a small model call
turns the message into a standalone search query and the search runs again.

The rewrite only feeds the search. It is never sent to the chat model as
something the user said and never saved as a turn, and the retriever's own
precision gates still decide what reaches the model."""

import logging
from typing import Any, Callable

from sympose import settings_store, vault_paths
from sympose.engine import budget, grounding, prompt
from sympose.engine import model as model_mod

log = logging.getLogger(__name__)

SETTING = "grounding_followups"
# Only an explicit "off" turns the step off; anything else, including the
# reserved "recent-words" and "model-searches", leaves the default.
_OFF = "off"
_RECENT_EXCHANGES = 2
_MAX_MESSAGE_CHARS = 300
_MAX_QUERY_TOKENS = 60

# Models that used the whole small reply limit thinking, so the step cannot
# work with them (a reasoning model took 9 to 11 s for nothing on every miss;
# it needs 20 to 130 s to finish): not asked again until the process restarts.
_CANNOT_REWRITE: set[str] = set()

Rewriter = Callable[[list[dict[str, str]], str, str, budget.Budget | None], str | None]


def enabled() -> bool:
    return settings_store.get(SETTING) != _OFF


def _prompt(history: list[dict[str, str]], message: str) -> list[dict[str, str]]:
    lines = [
        f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['content'][:_MAX_MESSAGE_CHARS]}"
        for turn in history[-2 * _RECENT_EXCHANGES :]
    ]
    body = "Conversation so far:\n" + "\n".join(lines) + f"\n\nLast message: {message}\n\nStandalone search query:"
    return [{"role": "system", "content": prompt.REWRITE_INSTRUCTIONS}, {"role": "user", "content": body}]


def rewrite_query(
    history: list[dict[str, str]], message: str, model: str, limits: budget.Budget | None
) -> str | None:
    """A standalone search query for `message`, or `None` when there is none
    to be had (the model says the message has no topic of its own, returned
    nothing, or failed, or the prompt would not fit the window)."""
    if model in _CANNOT_REWRITE:
        return None
    request = _prompt(history, message)
    if limits is not None and budget.count_tokens(request, model) > limits.prompt_tokens:
        return None
    try:
        # The chat's own window, so a local model is not reloaded for this call.
        reply = model_mod.call_model(
            request, model=model, num_ctx=limits.num_ctx if limits else None, max_tokens=_MAX_QUERY_TOKENS
        )
    except model_mod.ReplyLimitError as e:
        log.warning("'%s' cannot write a follow-up rewrite in its reply limit; not asking again: %s", model, e)
        _CANNOT_REWRITE.add(model)
        return None
    except model_mod.EngineModelError as e:
        log.warning("Follow-up rewrite failed, grounding on the message alone: %s", e)
        return None
    if reply.truncated:  # cut mid-word: searching on it could ground the wrong note
        return None
    lines = reply.text.strip().splitlines()
    query = lines[0].strip().strip("\"'") if lines else ""
    if not query or query.rstrip(".! ").upper() == prompt.NO_TOPIC:
        return None
    return query


def ground(
    persona: dict[str, Any],
    message: str,
    history: list[dict[str, str]],
    model: str,
    limits: budget.Budget | None,
    rewriter: Rewriter = rewrite_query,
) -> tuple[list[dict[str, Any]], str | None]:
    """`(passages, query)`: the passages for `message`, and, when they came
    from a rewritten query rather than the message itself, that query."""
    hits = grounding.ground(persona, message)
    if hits or not history or not enabled() or vault_paths.resolve_sandbox(persona) is None:
        return hits, None  # (no vault: nothing a rewritten query could find)
    query = rewriter(history, message, model, limits)
    if query is None or query == message:
        return [], None
    hits = grounding.ground(persona, query)
    return hits, (query if hits else None)
