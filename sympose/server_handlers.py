"""
Note/folder route handler logic for the dashboard API — split out of
`server.py` to keep that file to route registration only, out of
`server_models.py` to keep this file to logic only, and out of
`server_trash_handlers.py` to keep this file to the note/folder CRUD routes
only (project's 200-LOC-per-file guideline). `translate_vault_result` is
imported directly by `server_trash_handlers.py` too — it's the one
sentinel→HTTP translation every handler module shares.
"""

import os
from typing import Any

from fastapi import HTTPException

from sympose import (
    vault_graph,
    vault_paths,
    vault_write,
    vault_write_create,
    vault_write_delete,
    vault_write_rename,
)
from sympose.profile import resolve_profile
from sympose.server_models import FolderCreate, NoteCreate, NoteRename, NoteWrite
from sympose.vault_write_concurrency import NOTE_CONFLICT
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import (
    NOTE_DENIED,
    NOTE_EXISTS,
    NOTE_INVALID_NAME,
    NOTE_NOT_FOUND,
)


def translate_vault_result(
    result: str,
    *,
    not_found: str | None = None,
    exists: str | None = None,
    denied: str | None = None,
    conflict: str | None = None,
    invalid_name: str | None = None,
) -> None:
    """Raises the matching HTTPException for one of the vault write
    modules' shared sentinel outcomes, or returns None when `result` is a
    genuine success message. A caller passes only the sentinels it can
    actually hit."""
    if not_found is not None and result == NOTE_NOT_FOUND:
        raise HTTPException(status_code=404, detail=not_found)
    if exists is not None and result == NOTE_EXISTS:
        raise HTTPException(status_code=409, detail=exists)
    if denied is not None and result == NOTE_DENIED:
        raise HTTPException(status_code=403, detail=denied)
    if conflict is not None and result == NOTE_CONFLICT:
        raise HTTPException(status_code=409, detail=conflict)
    if invalid_name is not None and result == NOTE_INVALID_NAME:
        raise HTTPException(status_code=400, detail=invalid_name)
    if result.startswith("Error:"):
        raise HTTPException(status_code=500, detail=result)


def get_vault_tree(persona: str | None) -> dict[str, Any]:
    profile = resolve_profile(persona)
    return {
        "persona": persona,
        "tree": vault_graph.get_vault_tree(profile),
        "vaultName": vault_paths.get_vault_name(),
    }


def get_vault_graph() -> dict[str, Any]:
    return vault_graph.get_vault_graph()


def read_note(path: str, persona: str | None) -> dict[str, Any]:
    profile = resolve_profile(persona)
    target = resolve_existing_note(profile, path)
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"Note `{path}` not found in allowed vault folders."
        )
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            # Only trims the trailing newline(s) `overwrite_note`/`create_note`
            # always re-add on save — a full `.strip()` would also eat leading
            # blank lines, which then never come back once the note is saved.
            content = f.read().rstrip("\n")
            # `fstat` on the still-open descriptor, not a fresh `os.stat(target)`
            # after closing — that later call could race a concurrent delete/
            # replace and return a stale or missing mtime for content that was
            # in fact read successfully just above.
            mtime = os.fstat(f.fileno()).st_mtime
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error reading note `{path}`: {e}")
    return {"path": path, "content": content, "mtime": mtime}


def write_note(body: NoteWrite) -> dict[str, Any]:
    profile = resolve_profile(body.persona)
    result = vault_write.overwrite_note(
        profile, body.path, body.content, expected_mtime=body.expected_mtime
    )
    translate_vault_result(
        result,
        not_found=f"Note `{body.path}` not found in allowed vault folders.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
        conflict=f"Note `{body.path}` changed on disk since it was opened — reload before saving.",
    )
    return {"path": body.path, "detail": result}


def create_note(body: NoteCreate) -> dict[str, Any]:
    profile = resolve_profile(body.persona)
    result = vault_write_create.create_note(profile, body.path, body.content)
    translate_vault_result(
        result,
        exists=f"A note already exists at `{body.path}`.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
    )
    return {"path": body.path, "detail": result}


def create_folder(body: FolderCreate) -> dict[str, Any]:
    profile = resolve_profile(body.persona)
    result = vault_write_create.create_folder(profile, body.path)
    translate_vault_result(
        result,
        exists=f"A file or folder already exists at `{body.path}`.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
    )
    return {"path": body.path, "detail": result}


def rename_note(body: NoteRename) -> dict[str, Any]:
    profile = resolve_profile(body.persona)
    result = vault_write_rename.rename_note(profile, body.path, body.new_path)
    translate_vault_result(
        result,
        not_found=f"Note `{body.path}` not found in allowed vault folders.",
        exists=f"A note already exists at `{body.new_path}`.",
        denied=f"Path `{body.new_path}` is outside the assigned sandbox.",
        invalid_name="New name can't contain `[`, `]`, `|`, or `#` — those break wikilink syntax.",
    )
    return {"path": body.new_path, "detail": result}


def delete_note(path: str, persona: str | None) -> dict[str, Any]:
    profile = resolve_profile(persona)
    result = vault_write_delete.delete_note(profile, path)
    translate_vault_result(
        result,
        not_found=f"Note `{path}` not found in allowed vault folders.",
        denied=f"Path `{path}` is outside the assigned sandbox.",
    )
    return {"path": path, "detail": result}


def delete_folder(path: str, persona: str | None) -> dict[str, Any]:
    profile = resolve_profile(persona)
    result = vault_write_delete.delete_folder(profile, path)
    translate_vault_result(
        result,
        not_found=f"Folder `{path}` not found in allowed vault folders.",
        denied=f"Path `{path}` is outside the assigned sandbox.",
    )
    return {"path": path, "detail": result}
