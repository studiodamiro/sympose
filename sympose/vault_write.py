"""
Vault note/folder mutation: templates, create/write/append/overwrite,
rename (with wikilink retargeting), delete (to `.trash`), and the
daily/session-note writers built on top of them.

ADR-136: this used to be one ~990-line module; the actual logic now lives
in focused sibling modules (`vault_write_status.py`, `vault_write_resolve.py`,
`vault_write_core.py`, `vault_write_note.py`, `vault_write_create.py`,
`vault_write_delete.py`, `vault_write_rename.py`, `vault_write_daily.py`),
following the same "thin facade, satellite modules own the mechanics"
pattern ADR-125 already established for `vault.py`/`engine.py`. Every name
below is re-exported unchanged, so `vault.py` (the only caller that
accesses this module by name, e.g. `vault_write.write_note(...)`) needs no
changes at all.

Every function here does the filesystem mechanics and sandbox checks only —
re-indexing, manifest patching, and backlink-cache invalidation are the
caller's job, taken as optional hook parameters (`reindex_hook`,
`manifest_hook`, `on_backlinks_changed`) rather than imported directly. That
keeps this module free of any dependency on `sympose.vault` itself (which
already depends on this module — importing back would cycle), and matches
`vault_trash.py`'s existing pattern of "thin wrappers in vault.py own the
side effects, the satellite module owns the mechanics."
"""

from sympose.vault_write_concurrency import NOTE_CONFLICT, mtime_matches
from sympose.vault_write_core import get_template_for_path, overwrite_note
from sympose.vault_write_create import create_folder, create_note
from sympose.vault_write_daily import (
    sync_frontmatter_tags,
    write_daily_note,
    write_session_note,
)
from sympose.vault_write_delete import delete_folder, delete_note
from sympose.vault_write_note import append_note, write_note
from sympose.vault_write_rename import rename_note, rewrite_wikilink_targets
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND

__all__ = [
    "NOTE_CONFLICT",
    "NOTE_DENIED",
    "NOTE_EXISTS",
    "NOTE_NOT_FOUND",
    "append_note",
    "create_folder",
    "create_note",
    "delete_folder",
    "delete_note",
    "get_template_for_path",
    "mtime_matches",
    "overwrite_note",
    "rename_note",
    "resolve_existing_note",
    "rewrite_wikilink_targets",
    "sync_frontmatter_tags",
    "write_daily_note",
    "write_note",
    "write_session_note",
]
