"""
Note/folder route handler logic for the web API — split out of
`server.py` to keep that file to route registration only, out of
`server_models.py` to keep this file to logic only, and out of
`server_trash_handlers.py` to keep this file to the note/folder CRUD routes
only (project's 200-LOC-per-file guideline). `translate_vault_result`,
`sandbox_denied`, and `require_profile` are imported directly by
`server_trash_handlers.py`/`server_search_handlers.py` too — the one
sentinel→HTTP translation, the one denial message, and the one "reject an
unknown persona" check every handler module shares.
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
from sympose.profile import resolve_default_persona, resolve_profile
from sympose.server_models import FolderCreate, NoteCreate, NoteRename, NoteWrite
from sympose.vault_write_concurrency import NOTE_CONFLICT
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import (
    NOTE_DENIED,
    NOTE_EXISTS,
    NOTE_INVALID_NAME,
    NOTE_NOT_FOUND,
)


def _not_found(noun: str, path: str) -> str:
    return f"{noun} `{path}` not found in allowed vault folders."


def sandbox_denied(path: str) -> str:
    return f"Path `{path}` is outside the assigned sandbox."


def require_profile(persona: str | None) -> dict[str, Any]:
    """`resolve_profile`, raising 404 instead of returning `None` — every
    HTTP handler's one entry point for "resolve this request's persona or
    reject it." Distinct from `sandbox_denied`'s 403: that's a *valid*
    persona whose sandbox rejects a *path*; this is the persona itself
    not resolving to a profile at all."""
    profile = resolve_profile(persona)
    if profile is None:
        # `persona` itself, not the handle actually attempted -- an
        # omitted persona (None) resolves through the configured
        # default, and the message should name *that* handle, not
        # literally report "Unknown persona `None`."
        handle = persona or resolve_default_persona()
        raise HTTPException(status_code=404, detail=f"Unknown persona `{handle}`.")
    return profile


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
    profile = require_profile(persona)
    return {
        "persona": persona,
        "tree": vault_graph.get_vault_tree(profile),
        "vaultName": vault_paths.get_vault_name(),
    }


def get_vault_graph(persona: str | None) -> dict[str, Any]:
    return vault_graph.get_vault_graph(require_profile(persona))


def read_note(path: str, persona: str | None) -> dict[str, Any]:
    profile = require_profile(persona)
    target = resolve_existing_note(profile, path)
    if target is None:
        raise HTTPException(status_code=404, detail=_not_found("Note", path))
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
    except FileNotFoundError:
        # A concurrent delete landing between `resolve_existing_note`
        # returning this path and `open()` reaching it -- the note simply
        # isn't there anymore, not a server error.
        raise HTTPException(status_code=404, detail=_not_found("Note", path))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error reading note `{path}`: {e}")
    return {"path": path, "content": content, "mtime": mtime}


def write_note(body: NoteWrite) -> dict[str, Any]:
    profile = require_profile(body.persona)
    result = vault_write.overwrite_note(
        profile, body.path, body.content, expected_mtime=body.expected_mtime
    )
    translate_vault_result(
        result,
        not_found=_not_found("Note", body.path),
        denied=sandbox_denied(body.path),
        conflict=f"Note `{body.path}` changed on disk since it was opened — reload before saving.",
    )
    return {"path": body.path, "detail": result}


def create_note(body: NoteCreate) -> dict[str, Any]:
    profile = require_profile(body.persona)
    result = vault_write_create.create_note(profile, body.path, body.content)
    translate_vault_result(
        result,
        exists=f"A note already exists at `{body.path}`.",
        denied=sandbox_denied(body.path),
    )
    return {"path": body.path, "detail": result}


def create_folder(body: FolderCreate) -> dict[str, Any]:
    profile = require_profile(body.persona)
    result = vault_write_create.create_folder(profile, body.path)
    translate_vault_result(
        result,
        exists=f"A file or folder already exists at `{body.path}`.",
        denied=sandbox_denied(body.path),
    )
    return {"path": body.path, "detail": result}


def rename_note(body: NoteRename) -> dict[str, Any]:
    profile = require_profile(body.persona)
    result = vault_write_rename.rename_note(profile, body.path, body.new_path)
    translate_vault_result(
        result,
        not_found=_not_found("Note", body.path),
        exists=f"A note already exists at `{body.new_path}`.",
        denied=sandbox_denied(body.new_path),
        invalid_name="New name can't contain `[`, `]`, `|`, or `#` — those break wikilink syntax.",
    )
    return {"path": body.new_path, "detail": result}


def delete_note(path: str, persona: str | None) -> dict[str, Any]:
    profile = require_profile(persona)
    result = vault_write_delete.delete_note(profile, path)
    translate_vault_result(
        result,
        not_found=_not_found("Note", path),
        denied=sandbox_denied(path),
    )
    return {"path": path, "detail": result}


def delete_folder(path: str, persona: str | None) -> dict[str, Any]:
    profile = require_profile(persona)
    result = vault_write_delete.delete_folder(profile, path)
    translate_vault_result(
        result,
        not_found=_not_found("Folder", path),
        denied=sandbox_denied(path),
    )
    return {"path": path, "detail": result}
