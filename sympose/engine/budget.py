"""The context budget (docs/decisions/015): the engine sizes the prompt to the
model's window itself instead of relying on the runtime's silent cut, which
was measured to be able to remove the soul and the grounding rules.

Which window a turn gets is decided per turn from the model that actually
runs:
- a cloud model: the provider's window;
- an Ollama model, by default: its own maximum, capped at `AUTO_WINDOW_CEILING`;
- an Ollama model, if the user set `context_window`: that value, kept across
  model changes, never above what the model supports. It is sent to Ollama as
  `num_ctx`.

When the prompt does not fit, things are dropped in a fixed order: oldest
whole turns, then the lowest-scoring grounding passages, and never the soul,
the engine rules, or the new message. Nothing here calls a model."""

import logging
import math
from dataclasses import dataclass
from typing import Any, Callable

import litellm

from sympose import settings_store
from sympose.engine.model import EngineModelError

log = logging.getLogger(__name__)

# With no `context_window` setting a local model's window follows its own
# maximum, but never above this: a full-attention model with a 128k maximum
# would otherwise ask for many GB of memory on a machine that cannot spare it.
# A user who sets a larger number on purpose gets it.
AUTO_WINDOW_CEILING = 32768
# What a local model gets when its maximum cannot be read and the user set
# nothing: Ollama's own default, so nothing is asked of a model that may not
# support more.
UNKNOWN_MODEL_WINDOW = 4096
_SETTING = "context_window"
# Below this a window cannot hold even the shipped soul, so a smaller (or
# malformed) setting falls back to the default instead of failing every turn.
_MIN_CONTEXT_WINDOW = 1024
# Room kept for the reply, and the limit a local model's reply is held to. It
# scales with the window because a reasoning model spends its reply limit
# thinking (`qwen3:8b` on a hard question was cut off at 1024 and finished at
# 4096); `reply_limit` lets a user choose.
_MAX_AUTO_REPLY_TOKENS = 4096
_REPLY_SETTING = "reply_limit"
_MIN_REPLY_LIMIT = 64
# `litellm.token_counter` under-counts real tokens by up to about 12 percent
# on the measured local model (ADR 015); over-counting is the safe direction.
_TOKEN_MARGIN = 1.15
_OLLAMA_PREFIXES = ("ollama/", "ollama_chat/")

# A model's own maximum window, by model id: only successful lookups are
# kept, so a local server that was down for one turn is asked again.
_NATIVE_MAX: dict[str, int] = {}


class ContextTooSmallError(EngineModelError):
    """The soul, the engine rules and the new message alone do not fit the
    window: raised instead of letting the runtime cut them."""


@dataclass(frozen=True)
class Budget:
    prompt_tokens: int  # what the prompt may use, reply room already taken out
    num_ctx: int | None  # the window to ask Ollama for; `None` for cloud models
    reply_cap: int | None  # the reply's token limit; `None` when we do not cap it


@dataclass(frozen=True)
class Fitted:
    messages: list[dict[str, str]]
    grounding: list[dict[str, Any]]  # the passages that survived
    history_dropped: int  # turns left out for size, not counting the turn-count cap


def is_ollama(model: str) -> bool:
    return model.startswith(_OLLAMA_PREFIXES)


def context_setting() -> int | None:
    """The window the user chose on purpose, or `None` (automatic) when the
    setting is missing or not a positive whole number."""
    value = settings_store.get(_SETTING)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    # A small number is a request for a small footprint, so it is raised to
    # the smallest usable window and not treated as automatic (the opposite).
    return max(value, _MIN_CONTEXT_WINDOW)


def _native_max(model: str) -> int | None:
    if model in _NATIVE_MAX:
        return _NATIVE_MAX[model]
    try:
        value = litellm.get_model_info(model).get("max_input_tokens")
    except Exception as e:  # unknown model, or a local server that is not up
        log.debug("No window known for %s: %s", model, e)
        return None
    if isinstance(value, int) and value > 0:
        _NATIVE_MAX[model] = value
        return value
    return None


def window_for(model: str) -> int | None:
    """The window this model gets, or `None` when none is known (then no
    size trimming happens)."""
    native = _native_max(model)
    if not is_ollama(model):
        return native
    chosen = context_setting()
    if chosen is not None:  # the user's own ceiling, kept across model changes
        return min(chosen, native) if native else chosen
    return min(native, AUTO_WINDOW_CEILING) if native else UNKNOWN_MODEL_WINDOW


def reply_reserve(window: int) -> int:
    """Tokens kept for the reply: the user's `reply_limit` (never more than
    half the window), else a quarter of the window up to a fixed ceiling."""
    value = settings_store.get(_REPLY_SETTING)
    if isinstance(value, int) and value >= _MIN_REPLY_LIMIT:  # a bool is 0 or 1: too small
        return min(value, window // 2)
    return min(_MAX_AUTO_REPLY_TOKENS, window // 4)


def budget_for(model: str) -> Budget | None:
    window = window_for(model)
    if window is None:
        return None
    # Room for the reply comes out of the window for every model, since some
    # providers share one window between input and output; only a local
    # model's reply is also capped to it.
    reserve = reply_reserve(window)
    if not is_ollama(model):
        return Budget(prompt_tokens=window - reserve, num_ctx=None, reply_cap=None)
    return Budget(prompt_tokens=window - reserve, num_ctx=window, reply_cap=reserve)


def _count_raw(messages: list[dict[str, str]], model: str) -> int:
    try:
        return litellm.token_counter(model=model, messages=messages)
    except Exception as e:
        log.warning("Token count failed for %s (%s); estimating from length", model, e)
        # One token per character: an upper bound even for dense text (CJK),
        # so a failing counter can only make the trimming too eager, never
        # let an overflow through.
        return sum(len(m["content"]) + 4 for m in messages)


def count_tokens(messages: list[dict[str, str]], model: str) -> int:
    return math.ceil(_count_raw(messages, model) * _TOKEN_MARGIN)


def fit(
    build_messages: Callable[[list[dict[str, str]], list[dict[str, Any]]], list[dict[str, str]]],
    history: list[dict[str, str]],
    grounding: list[dict[str, Any]],
    model: str,
    prompt_tokens: int,
) -> Fitted:
    """`build_messages(history, grounding)` assembles the whole prompt, so
    the soul, the rules and the new message are always in it. `history` is
    `user, assistant` pairs, oldest first; `grounding` is best-first."""
    kept_history, kept_grounding = list(history), list(grounding)
    dropped = 0

    def attempt() -> tuple[list[dict[str, str]], int]:
        messages = build_messages(kept_history, kept_grounding)
        return messages, count_tokens(messages, model)

    messages, used = attempt()
    while used > prompt_tokens and kept_history:
        del kept_history[:2]
        dropped += 1
        messages, used = attempt()
    while used > prompt_tokens and kept_grounding:
        kept_grounding.pop()
        messages, used = attempt()
    if used > prompt_tokens:
        raise ContextTooSmallError(
            f"This persona's instructions and your message need about {used} tokens, but "
            f"'{model}' leaves {prompt_tokens} for them. If your message is very long, "
            f"shorten it; otherwise use a model with a larger window (and if you set "
            f"`{_SETTING}`, raise it)."
        )
    return Fitted(messages, kept_grounding, dropped)
