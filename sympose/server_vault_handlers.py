"""
Vault-list / active-vault / add-vault route handler logic for the dashboard
API — the workspace switcher (ADR 003, ADR 004). Split out the same way
search and the bin are, to keep each handler module to one concern
(project's 200-LOC-per-file guideline).
"""

from typing import Any

from fastapi import HTTPException

from sympose import vault_registry


def list_vaults() -> dict[str, Any]:
    active = vault_registry.get_active_vault_path()
    return {
        "vaults": vault_registry.get_configured_vaults(),
        "active": active,
    }


def set_active_vault(path: str) -> dict[str, Any]:
    if not vault_registry.set_active_vault(path):
        raise HTTPException(
            status_code=404,
            detail="Not a configured vault — check VAULT_PATHS.",
        )
    return list_vaults()


def add_vault(path: str) -> dict[str, Any]:
    """Adds and activates `path` — the switcher's add-path input makes the
    newly added vault active immediately rather than leaving it configured
    but unselected, so typing a path and hitting Enter is the whole flow."""
    vault = vault_registry.add_vault(path)
    if vault is None:
        raise HTTPException(
            status_code=400,
            detail="Couldn't add that vault — check the path exists and is "
            "a folder.",
        )
    vault_registry.set_active_vault(vault["path"])
    return list_vaults()
