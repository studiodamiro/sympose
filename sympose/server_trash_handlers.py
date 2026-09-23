"""
Trash-recovery route handlers — split out of `server_handlers.py` (project's
200-LOC-per-file guideline).
"""

from typing import Any

from fastapi import HTTPException

from sympose import vault_paths, vault_trash
from sympose.profile import resolve_profile
from sympose.server_handlers import sandbox_denied, translate_vault_result
from sympose.server_models import TrashEmpty, TrashRestore


def _not_in_bin(path: str) -> str:
    return f"`{path}` is not in the bin."


def _trash_scope(persona: str | None) -> tuple[str | None, list[str]]:
    profile = resolve_profile(persona)
    return vault_paths.get_master_vault(), vault_paths.get_allowed_dirs(profile)


def _require_trash_scope(persona: str | None) -> tuple[str, list[str]]:
    """Same as `_trash_scope`, but raises 403 instead of returning an
    empty/falsy scope — for the mutating routes, where "nothing configured"
    is an error, not an empty result."""
    mv, allowed_dirs = _trash_scope(persona)
    if not mv or not allowed_dirs:
        raise HTTPException(status_code=403, detail="No vault configured for this persona.")
    return mv, allowed_dirs


def list_trash(persona: str | None) -> dict[str, Any]:
    mv, allowed_dirs = _trash_scope(persona)
    if not mv or not allowed_dirs:
        return {"items": []}
    return {"items": vault_trash.list_trashed(mv, allowed_dirs)}


def restore_trash(body: TrashRestore) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(body.persona)
    result = vault_trash.restore(mv, allowed_dirs, body.path)
    translate_vault_result(
        result,
        not_found=_not_in_bin(body.path),
        exists="Something already occupies that note's original location.",
        denied=sandbox_denied(body.path),
    )
    return {"path": result, "detail": f"Restored to `{result}`"}


def purge_trash(path: str, persona: str | None) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(persona)
    result = vault_trash.purge(mv, allowed_dirs, path)
    translate_vault_result(
        result,
        not_found=_not_in_bin(path),
        denied=sandbox_denied(path),
    )
    return {"path": path, "detail": "Deleted permanently."}


def empty_trash(body: TrashEmpty) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(body.persona)
    count = vault_trash.purge_all(mv, allowed_dirs)
    return {
        "count": count,
        "detail": f"Emptied the bin ({count} note{'' if count == 1 else 's'}).",
    }
