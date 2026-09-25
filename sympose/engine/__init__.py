"""The chat engine (docs/decisions/006, docs/decisions/007) — `run_turn` is
the one entrypoint every channel (CLI today; Slack/web later) calls."""

from sympose.engine.model import EngineModelError
from sympose.engine.recap_refresh import refresh_in_background as refresh_recaps
from sympose.engine.semantic_refresh import refresh_in_background as refresh_embeddings
from sympose.engine.turn import PersonaNotFoundError, TurnResult, run_turn

__all__ = ["run_turn", "TurnResult", "EngineModelError", "PersonaNotFoundError", "refresh_recaps", "refresh_embeddings"]
