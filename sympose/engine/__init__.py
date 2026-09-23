"""The chat engine (docs/decisions/006, docs/decisions/007) — `run_turn` is
the one entrypoint every channel (CLI today; Slack/dashboard later) calls."""

from sympose.engine.model import EngineModelError
from sympose.engine.turn import PersonaNotFoundError, TurnResult, run_turn

__all__ = ["run_turn", "TurnResult", "EngineModelError", "PersonaNotFoundError"]
