"""
Shared sentinels and no-op hook defaults for vault_write.py's split modules
(ADR-136) — split out first since every other vault_write_*.py module
imports from here, and this one imports from none of them.
"""

from typing import Callable

# Mapped onto VaultManager.NOTE_* (same values) so the server sees one
# consistent status vocabulary regardless of which module a result
# actually came from.
NOTE_NOT_FOUND = "__note_not_found__"
NOTE_DENIED = "__note_denied__"
NOTE_EXISTS = "__note_exists__"

_NOOP_HOOK: Callable[[str, str], None] = lambda mv, path: None  # noqa: E731
_NOOP_CALLBACK: Callable[[], None] = lambda: None  # noqa: E731
