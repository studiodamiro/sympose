"""
Reading a note or asset by name from the sandboxed vault, each via the same
three-tier lookup: a direct join against the vault root, the bare filename
inside an allowed dir, then a recursive match anywhere under one.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(NoteReadMixin, ...)` is a pure move, not a
rewrite. Depends on `cls._get_master_vault`, `cls.get_allowed_dirs`, and
`cls._get_vault_snapshot` (from `vault_snapshot.SnapshotMixin`), all
resolved normally through the MRO once `VaultManager` inherits from this
mixin, no parameter threading needed.
"""

import os
from typing import Any

from sympose.config import is_safe_path


class NoteReadMixin:
    @classmethod
    def read_note(cls, profile: dict[str, Any], note_name: str) -> str:
        """Reads a note by name from the sandboxed vault, trying each tier
        below in order: a direct vault-root path, the bare filename inside
        an allowed dir, then a recursive case-insensitive stem match."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        clean_name = note_name.strip().strip("\"'")
        if not clean_name.endswith(".md"):
            clean_name += ".md"

        hit = cls._read_note_direct(mv, allowed_dirs, clean_name)
        if hit is not None:
            return hit
        hit = cls._read_note_by_basename(allowed_dirs, clean_name)
        if hit is not None:
            return hit
        hit = cls._read_note_recursive(mv, allowed_dirs, clean_name)
        if hit is not None:
            return hit
        return f"Note `{clean_name}` not found in allowed vault folders."

    @classmethod
    def _read_note_direct(
        cls, mv: str, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 1 - the note at the vault root, under an allowed dir."""
        direct_target = os.path.join(mv, clean_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                try:
                    with open(
                        direct_target, "r", encoding="utf-8", errors="replace"
                    ) as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{clean_name}`: {e}"
        return None

    @classmethod
    def _read_note_by_basename(
        cls, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 2 - the note's bare filename directly inside an allowed dir."""
        for allowed in allowed_dirs:
            target = os.path.join(allowed, os.path.basename(clean_name))
            if is_safe_path(target, allowed) and os.path.exists(target):
                try:
                    with open(target, "r", encoding="utf-8", errors="replace") as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{clean_name}`: {e}"
        return None

    @classmethod
    def _read_note_recursive(
        cls, mv: str, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 3 - recursive case-insensitive / title lookup in allowed
        folders. Routed through the cached vault snapshot (E7) rather than a
        fresh os.walk + re-read - the same content `get_folder_digest` and
        `search_structured` already reuse, now safe to share here too since
        D6 made the underlying cache actually notice an in-place content
        edit, not just directory-level add/remove/rename."""
        stem_target = os.path.splitext(os.path.basename(clean_name))[0].lower()
        for entry in cls._get_vault_snapshot(mv, allowed_dirs):
            if os.path.splitext(entry["file_name"])[0].lower() == stem_target:
                return entry["full_content"].strip()
        return None

    @classmethod
    def resolve_asset_path(cls, profile: dict[str, Any], asset_name: str) -> str | None:
        """Resolves a `![[ref]]` embed reference to an absolute file path within
        the persona's sandbox — same three-tier lookup as `read_note` (direct
        join, basename in each allowed dir, recursive walk), but for any file
        and matched on the full filename rather than a bare stem, since an
        asset ref always carries its extension (`diagram.png`, not `diagram`).
        Deliberately does not consult `vault.ignore_folders`: that list exists
        to keep attachment folders out of the *note* index/search/backlinks,
        and its own default names "Attachments" — exactly where embedded
        images typically live, so applying it here would make them
        unreachable. Only dot-directories (`.git`, `.obsidian`, `.trash`, …)
        are skipped."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None
        clean_name = asset_name.strip().strip("\"'")
        if not clean_name:
            return None

        return (
            cls._resolve_asset_direct(mv, allowed_dirs, clean_name)
            or cls._resolve_asset_by_basename(allowed_dirs, clean_name)
            or cls._resolve_asset_recursive(allowed_dirs, clean_name)
        )

    @classmethod
    def _resolve_asset_direct(
        cls, mv: str, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 1 - a direct join against the vault root."""
        direct_target = os.path.join(mv, clean_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.isfile(direct_target):
                return direct_target
        return None

    @classmethod
    def _resolve_asset_by_basename(
        cls, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 2 - the asset's bare filename directly inside an allowed dir."""
        for allowed in allowed_dirs:
            target = os.path.join(allowed, os.path.basename(clean_name))
            if is_safe_path(target, allowed) and os.path.isfile(target):
                return target
        return None

    @classmethod
    def _resolve_asset_recursive(
        cls, allowed_dirs: list[str], clean_name: str
    ) -> str | None:
        """Tier 3 - recursive filename match anywhere under an allowed dir."""
        want = os.path.basename(clean_name).lower()
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    if fn.lower() == want:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return fp
        return None
