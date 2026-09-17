"""
Resolving a note "target" string — an index number from the last search, a
relative path, or a bare filename — to its (rel_path, abs_path), plus
opening the resolved note in Obsidian/the system default editor.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(NoteTargetMixin, ...)` is a pure move, not a
rewrite. Depends on `cls._get_master_vault`, `cls.get_allowed_dirs`, and
`cls.resolve_note_target`, all resolved normally through the MRO once
`VaultManager` inherits from this mixin, no parameter threading needed.
"""

import os
from typing import Any

from sympose import vault_search
from sympose.config import config_manager, is_safe_path


class NoteTargetMixin:
    @classmethod
    def resolve_note_target(
        cls, profile: dict[str, Any], target: str
    ) -> tuple[str | None, str | None]:
        """Resolves target string (index number, relative path, or filename)
        to (rel_path, abs_path). Tries each case below in order; the first
        that resolves wins."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return None, None

        clean_target = target.strip().strip("\"'")
        cached = vault_search.get_last_search(profile)

        hit = (
            cls._resolve_target_by_index(cached, clean_target)
            or cls._resolve_target_from_cache(cached, clean_target)
            or cls._resolve_target_directly(mv, allowed_dirs, clean_target)
            or cls._resolve_target_recursively(mv, allowed_dirs, clean_target)
        )
        return hit if hit else (None, None)

    @classmethod
    def _resolve_target_by_index(
        cls, cached: list[dict[str, Any]], clean_target: str
    ) -> tuple[str, str] | None:
        """Case 1 - a bare number like "3" indexes into the last search's
        results."""
        if clean_target.isdigit():
            idx = int(clean_target)
            for item in cached:
                if item.get("index") == idx:
                    return item.get("rel_path"), item.get("abs_path")
        return None

    @classmethod
    def _resolve_target_from_cache(
        cls, cached: list[dict[str, Any]], clean_target: str
    ) -> tuple[str, str] | None:
        """Case 2 - an exact rel_path or filename-stem match among the last
        search's results."""
        t_stem = os.path.splitext(os.path.basename(clean_target))[0].lower()
        for item in cached:
            if (
                item.get("rel_path", "").lower() == clean_target.lower()
                or os.path.splitext(item.get("file_name", ""))[0].lower() == t_stem
            ):
                return item.get("rel_path"), item.get("abs_path")
        return None

    @classmethod
    def _resolve_target_directly(
        cls, mv: str, allowed_dirs: list[str], clean_target: str
    ) -> tuple[str, str] | None:
        """Case 3 - a direct lookup of the target (a .md/.txt extension is
        inferred if missing) at the vault root or an allowed dir's own top
        level."""
        target_name = (
            clean_target
            if clean_target.endswith((".md", ".txt"))
            else clean_target + ".md"
        )
        direct_target = os.path.join(mv, target_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                return os.path.relpath(direct_target, mv), direct_target
        for allowed in allowed_dirs:
            candidate = os.path.join(allowed, os.path.basename(target_name))
            if is_safe_path(candidate, allowed) and os.path.exists(candidate):
                return os.path.relpath(candidate, mv), candidate
        return None

    @classmethod
    def _resolve_target_recursively(
        cls, mv: str, allowed_dirs: list[str], clean_target: str
    ) -> tuple[str, str] | None:
        """Case 4 - recursive filename-stem match anywhere under an allowed
        dir."""
        t_stem = os.path.splitext(os.path.basename(clean_target))[0].lower()
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for allowed in allowed_dirs:
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for fn in files:
                    if os.path.splitext(fn)[0].lower() == t_stem:
                        fp = os.path.join(root, fn)
                        if is_safe_path(fp, allowed):
                            return os.path.relpath(fp, mv), fp
        return None

    @classmethod
    def open_in_obsidian(cls, profile: dict[str, Any], target: str) -> tuple[bool, str]:
        """Opens note in Obsidian desktop app / system default editor."""
        import platform
        import subprocess

        rel_path, abs_path = cls.resolve_note_target(profile, target)
        if not abs_path or not os.path.exists(abs_path):
            return False, f"⚠️ Note `{target}` not found in allowed vault folders."

        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", abs_path])
            elif system == "Linux":
                subprocess.Popen(["xdg-open", abs_path])
            elif system == "Windows":
                os.startfile(abs_path)
            return True, f"✨ Opened `{rel_path}` in Obsidian / system editor."
        except Exception as e:
            return False, f"⚠️ Failed to open note: {e}"
