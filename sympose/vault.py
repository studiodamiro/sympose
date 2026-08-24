"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import os
import datetime
from typing import Dict, Any, Optional, List
from sympose.config import is_safe_path


class VaultManager:
    """Manages sandboxed reading, writing, and multi-folder searching inside Obsidian vault directories."""

    @staticmethod
    def _get_master_vault() -> Optional[str]:
        mv = os.getenv("MASTER_VAULT_PATH")
        return os.path.abspath(os.path.expanduser(mv)) if mv else None

    @classmethod
    def get_allowed_dirs(cls, profile: Dict[str, Any]) -> List[str]:
        """Resolves list of permitted folder paths (supports multi-folder whitelist or full-vault root)."""
        mv = cls._get_master_vault()
        if not mv:
            return []
        try:
            os.makedirs(mv, exist_ok=True)
            folders = profile.get("vault_folders")
            if folders is None:
                single = profile.get("vault_folder", "")
                folders = [single]

            if "" in folders or "*" in folders or "all" in folders:
                return [mv]

            allowed = []
            for f in folders:
                path = os.path.join(mv, f.strip()) if f.strip() else mv
                if is_safe_path(path, mv):
                    os.makedirs(path, exist_ok=True)
                    allowed.append(path)
            return allowed or [mv]
        except Exception:
            return []

    @classmethod
    def get_primary_dir(cls, profile: Dict[str, Any]) -> Optional[str]:
        dirs = cls.get_allowed_dirs(profile)
        return dirs[0] if dirs else None

    @classmethod
    def read_note(cls, profile: Dict[str, Any], note_name: str) -> str:
        """Reads note from any of the persona's allowed directories."""
        mv = cls._get_master_vault()
        allowed_dirs = cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory (`MASTER_VAULT_PATH`) not configured or access denied."

        if not note_name.endswith(".md"):
            note_name += ".md"

        # Check direct path relative to master_vault
        direct_target = os.path.join(mv, note_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                try:
                    with open(direct_target, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{note_name}`: {e}"

        # Check relative to each allowed folder
        for allowed in allowed_dirs:
            target = os.path.join(allowed, os.path.basename(note_name))
            if is_safe_path(target, allowed) and os.path.exists(target):
                try:
                    with open(target, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{note_name}`: {e}"

        return f"Note `{note_name}` not found in allowed vault folders."

    @classmethod
    def search(cls, profile: Dict[str, Any], query: str) -> str:
        """Searches for notes matching query across all allowed directories."""
        mv = cls._get_master_vault()
        allowed_dirs = cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory (`MASTER_VAULT_PATH`) not configured or access denied."

        query_lower = query.lower()
        matches = []
        try:
            for allowed in allowed_dirs:
                for root, _, files in os.walk(allowed):
                    for file in files:
                        if file.endswith(".md"):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, mv)
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in file.lower():
                                    matches.append(f"**{rel_path}** (Title match):\n{content[:1200].strip()}")
                                elif query_lower in content.lower():
                                    matches.append(f"**{rel_path}** (Content match):\n{content[:1200].strip()}")
                            if len(matches) >= 4:
                                break
                    if len(matches) >= 4:
                        break
        except Exception as e:
            return f"Error searching vault: {e}"

        return "\n\n---\n\n".join(matches) if matches else f"No notes found matching `{query}` in allowed vault folders."

    @classmethod
    def write_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        """Writes note to specified path or primary allowed directory."""
        mv = cls._get_master_vault()
        allowed_dirs = cls.get_allowed_dirs(profile)
        primary_dir = cls.get_primary_dir(profile)
        if not mv or not primary_dir:
            return "Warning: Master notes directory (`MASTER_VAULT_PATH`) not configured or path denied."

        if not note_name.endswith(".md"):
            note_name += ".md"

        # Determine target file location
        if "/" in note_name or "\\" in note_name:
            target_file = os.path.join(mv, note_name)
        else:
            target_file = os.path.join(primary_dir, note_name)

        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return f"Security Error: Target path `{note_name}` is outside assigned sandbox."

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M")
        rel_display = os.path.relpath(target_file, mv)

        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            is_new = not os.path.exists(target_file)
            with open(target_file, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(
                        f"---\nentry: {date_str}\ncreated: {time_str}\ntype: note\n"
                        f"project: sympose\nauthor: {profile.get('name', 'sympose')}\n---\n\n"
                        f"# {os.path.splitext(os.path.basename(note_name))[0]}\n\n"
                    )
                f.write(f"\n{content.strip()}\n")
            return f"Saved to note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"

    @classmethod
    def append_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        return cls.write_note(profile, note_name, content)

    @classmethod
    def write_daily_note(cls, profile: Dict[str, Any], reflection: str) -> str:
        now = datetime.datetime.now()
        note_name = os.path.join("Daily Notes", f"{now.strftime('%Y-%m-%d')}.md")
        return cls.write_note(profile, note_name, f"\n### Reflection ({now.strftime('%H:%M')})\n{reflection}")

    @classmethod
    def write_session_note(
        cls, profile: Dict[str, Any], summary_md: str, subfolder: str = "Sessions", session_title: Optional[str] = None
    ) -> str:
        primary_dir = cls.get_primary_dir(profile)
        mv = cls._get_master_vault()
        if not primary_dir or not mv:
            return "Warning: Master notes directory not configured or path denied."

        now = datetime.datetime.now()
        handle = profile.get("handle", "agent").lower()
        title_slug = f"_{session_title.lower().replace(' ', '_')}" if session_title else ""
        filename = f"{now.strftime('%Y-%m-%d_%H%M')}_{handle}{title_slug}_session.md"
        target_dir = os.path.join(primary_dir, subfolder)
        target_file = os.path.join(target_dir, filename)

        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(
                    f"---\nentry: {now.strftime('%Y-%m-%d')}\ncreated: {now.strftime('%Y-%m-%d %H:%M')}\n"
                    f"type: session-log\nproject: sympose\nauthor: {profile.get('name', handle)}\n"
                    f"tags:\n  - session/log\n  - sympose/{handle}\n---\n\n"
                    f"# Session Log: {profile.get('name', handle)} ({now.strftime('%Y-%m-%d %H:%M')})\n\n{summary_md.strip()}\n"
                )
            rel_display = os.path.relpath(target_file, mv)
            return f"Saved session note to Obsidian: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write session note: {e}"
