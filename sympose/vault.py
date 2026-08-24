"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import os
import datetime
from typing import Dict, Any, Optional
from sympose.config import is_safe_path


class VaultManager:
    """Manages sandboxed reading and writing inside the persona's allowed domain directory."""

    @staticmethod
    def get_allowed_dir(profile: Dict[str, Any]) -> Optional[str]:
        master_vault = os.getenv("MASTER_VAULT_PATH")
        if not master_vault:
            return None

        try:
            os.makedirs(master_vault, exist_ok=True)
            vault_folder = profile.get("vault_folder", "")
            allowed_dir = os.path.join(master_vault, vault_folder) if vault_folder else master_vault
            os.makedirs(allowed_dir, exist_ok=True)

            if not is_safe_path(allowed_dir, master_vault):
                return None
            return allowed_dir
        except Exception:
            return None

    @classmethod
    def search(cls, profile: Dict[str, Any], query: str) -> str:
        master_vault = os.getenv("MASTER_VAULT_PATH")
        if not master_vault or not os.path.exists(master_vault):
            return "⚠️ Master notes directory (`MASTER_VAULT_PATH`) is not configured or does not exist."

        allowed_dir = cls.get_allowed_dir(profile)
        vault_folder = profile.get("vault_folder", "")
        if not allowed_dir:
            return f"⚠️ Access denied or folder `{vault_folder}` invalid."

        query_lower = query.lower()
        matches = []

        try:
            for root, _, files in os.walk(allowed_dir):
                for file in files:
                    if file.endswith(".md"):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, allowed_dir)
                        if query_lower in file.lower():
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                excerpt = f.read(1500).strip()
                                matches.append(f"**{rel_path}** (Title match):\n{excerpt}")
                                if len(matches) >= 2:
                                    break
                        else:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in content.lower():
                                    snippet = content[:1200].strip()
                                    matches.append(f"**{rel_path}** (Content match):\n{snippet}")
                                    if len(matches) >= 2:
                                        break
                if len(matches) >= 2:
                    break
        except Exception as e:
            return f"Error searching vault: {e}"

        if not matches:
            return f"No notes found matching `{query}` in `{vault_folder}/`."

        return "\n\n---\n\n".join(matches)

    @classmethod
    def write_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        """Writes or appends structured Markdown content inside the persona's sandboxed folder."""
        allowed_dir = cls.get_allowed_dir(profile)
        vault_folder = profile.get("vault_folder", "")
        if not allowed_dir:
            return "Warning: Master notes directory (`MASTER_VAULT_PATH`) not configured or path denied."

        if not note_name.endswith(".md"):
            note_name += ".md"

        target_file = os.path.join(allowed_dir, note_name)
        if not is_safe_path(target_file, allowed_dir):
            return "Security Error: Target file path is outside assigned sandbox."

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M")

        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            is_new = not os.path.exists(target_file)

            with open(target_file, "a", encoding="utf-8") as f:
                if is_new:
                    # Write clean Obsidian YAML frontmatter
                    f.write(
                        f"---\n"
                        f"entry: {date_str}\n"
                        f"created: {time_str}\n"
                        f"type: note\n"
                        f"project: sympose\n"
                        f"author: {profile.get('name', 'sympose')}\n"
                        f"---\n\n"
                        f"# {os.path.splitext(os.path.basename(note_name))[0]}\n\n"
                    )
                f.write(f"\n{content.strip()}\n")

            return f"Saved to note: `{vault_folder}/{note_name}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"

    @classmethod
    def write_daily_note(cls, profile: Dict[str, Any], reflection: str) -> str:
        """Appends a daily reflection into Daily Notes/YYYY-MM-DD.md in the sandboxed folder."""
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        note_name = os.path.join("Daily Notes", f"{date_str}.md")
        timestamp_header = f"\n### Reflection ({now.strftime('%H:%M')})\n"
        return cls.write_note(profile, note_name, timestamp_header + reflection)

    @classmethod
    def write_session_note(
        cls,
        profile: Dict[str, Any],
        summary_md: str,
        subfolder: str = "Sessions",
        session_title: Optional[str] = None
    ) -> str:
        """Writes a structured session log markdown file into {allowed_dir}/{subfolder}/."""
        allowed_dir = cls.get_allowed_dir(profile)
        vault_folder = profile.get("vault_folder", "")
        if not allowed_dir:
            return "Warning: Master notes directory (`MASTER_VAULT_PATH`) not configured or path denied."

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M")
        file_time_str = now.strftime("%Y-%m-%d_%H%M")
        handle = profile.get("handle", "agent").lower()

        title_slug = f"_{session_title.lower().replace(' ', '_')}" if session_title else ""
        filename = f"{file_time_str}_{handle}{title_slug}_session.md"
        target_dir = os.path.join(allowed_dir, subfolder)
        target_file = os.path.join(target_dir, filename)

        if not is_safe_path(target_file, allowed_dir):
            return "Security Error: Target file path is outside assigned sandbox."

        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                # Write standard Obsidian YAML frontmatter
                f.write(
                    f"---\n"
                    f"entry: {date_str}\n"
                    f"created: {time_str}\n"
                    f"type: session-log\n"
                    f"project: sympose\n"
                    f"author: {profile.get('name', handle)}\n"
                    f"tags:\n"
                    f"  - session/log\n"
                    f"  - sympose/{handle}\n"
                    f"---\n\n"
                    f"# Session Log: {profile.get('name', handle)} ({time_str})\n\n"
                    f"{summary_md.strip()}\n"
                )
            rel_path = f"{vault_folder}/{subfolder}/{filename}" if vault_folder else f"{subfolder}/{filename}"
            return f"Saved session note to Obsidian: `{rel_path}`"
        except Exception as e:
            return f"Error: Failed to write session note: {e}"
