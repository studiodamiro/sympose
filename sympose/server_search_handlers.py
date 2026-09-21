"""
Search route handler logic for the dashboard API — split out of
`server_handlers.py` the same way the bin's routes are, to keep each
handler module to one concern (project's 200-LOC-per-file guideline).
"""

from typing import Any

from sympose import vault_search
from sympose.profile import resolve_profile


def search_vault(query: str, folder: str | None, persona: str | None) -> dict[str, Any]:
    profile = resolve_profile(persona)
    return {
        "query": query,
        "results": vault_search.search_structured(profile, query, target_folder=folder),
    }
