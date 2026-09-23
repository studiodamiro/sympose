"""
Persona-roster route handler — split out of `server_handlers.py` the same
way the bin's and search's routes are (project's 200-LOC-per-file
guideline). Matches `ui/src/lib/personas.ts`'s `PersonasResponse` contract
exactly, which the dashboard already calls and gracefully falls back from
when unreachable — this route is what makes that live instead of static.
"""

from typing import Any

from sympose.engine.model import resolve_model
from sympose.profile import list_profiles, resolve_default_persona


def get_personas() -> dict[str, Any]:
    default_handle = resolve_default_persona()
    fallback_model = resolve_model()  # read once, not per persona
    return {
        "default": default_handle,
        "personas": [
            {
                "handle": p["handle"],
                "name": p["name"],
                "title": p["title"],
                "model": p["model"] or fallback_model,
                "skills": p["skills"],
                "is_default": p["handle"] == default_handle,
            }
            for p in list_profiles()
        ],
    }
