"""How many tokens a small helper call (the follow-up rewrite, ADR 017, and the recap,
ADR 023) may write, by kind of model (docs/decisions/007).

A local model gets the small limit: it keeps a thinking model from spending a minute on a
task worth a sentence (and the step is switched off for that model when it does). A cloud
model gets room: its thinking counts against the same limit, so a small one returned
nothing and was billed for it. The limit is a ceiling; only the tokens used are billed."""

from sympose import settings_store
from sympose.engine import budget

_SETTING = "cloud_helper_limit"
DEFAULT_CLOUD_TOKENS = 4000
_MIN_TOKENS = 64


def cloud_limit() -> int:
    """The user's `cloud_helper_limit`, else the default; a bool is 0 or 1 and a number too
    small to hold an answer is no better than the small limit, so both mean the default."""
    value = settings_store.get(_SETTING)
    return value if isinstance(value, int) and value >= _MIN_TOKENS else DEFAULT_CLOUD_TOKENS


def for_model(model: str, local_limit: int) -> int:
    return local_limit if budget.is_ollama(model) else cloud_limit()
