"""
Autonomic Action Tag Processor for Sympose Agents.
"""

import re
from typing import Dict, Any, List, Tuple
from sympose.vault import VaultManager


class ActionProcessor:
    """Parses, executes, and badges autonomic model action tags ([REMEMBER], [WRITE_NOTE], etc.)."""

    # Tag Regex Patterns
    PATTERNS = {
        "WRITE_NOTE": re.compile(r"\[(?:ACTION:)?WRITE_NOTE:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "APPEND_NOTE": re.compile(r"\[(?:ACTION:)?APPEND_NOTE:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "DAILY_NOTE": re.compile(r"\[(?:ACTION:)?DAILY_NOTE:\s*([\s\S]+?)\]", re.IGNORECASE),
        "REMEMBER": re.compile(r"\[(?:ACTION:)?REMEMBER:\s*([^\]]+?)\]", re.IGNORECASE),
    }

    @classmethod
    def execute_actions(cls, profile_manager: Any, handle: str, text: str) -> Tuple[str, List[str]]:
        """Executes all detected action tags in model output and returns (clean_text, confirmation_badges)."""
        profile = profile_manager.get_profile(handle)
        if not profile:
            return text, []

        badges: List[str] = []
        name = profile.get("name", handle)
        vault_folder = profile.get("vault_folder", "")
        is_shared = profile.get("share_memory", False)

        # 1. WRITE_NOTE Tags
        for match in cls.PATTERNS["WRITE_NOTE"].finditer(text):
            filename = match.group(1).strip()
            content = match.group(2).strip()
            if filename and content:
                res = VaultManager.write_note(profile, filename, content)
                rel_path = f"{vault_folder}/{filename}" if vault_folder else filename
                if not rel_path.endswith(".md"):
                    rel_path += ".md"
                badges.append(f"> 📝 **{name} saved note to Vault:** `{rel_path}`")

        # 2. APPEND_NOTE Tags
        for match in cls.PATTERNS["APPEND_NOTE"].finditer(text):
            filename = match.group(1).strip()
            content = match.group(2).strip()
            if filename and content:
                res = VaultManager.append_note(profile, filename, content)
                rel_path = f"{vault_folder}/{filename}" if vault_folder else filename
                if not rel_path.endswith(".md"):
                    rel_path += ".md"
                badges.append(f"> 📝 **{name} appended to Vault note:** `{rel_path}`")

        # 3. DAILY_NOTE Tags
        for match in cls.PATTERNS["DAILY_NOTE"].finditer(text):
            reflection = match.group(1).strip()
            if reflection:
                VaultManager.write_daily_note(profile, reflection)
                badges.append(f"> 📅 **{name} logged entry to Daily Notes**")

        # 4. REMEMBER Tags
        for match in cls.PATTERNS["REMEMBER"].finditer(text):
            fact = match.group(1).strip()
            if fact:
                profile_manager.append_memory(handle, fact)
                mem_desc = "working & shared team memory" if is_shared else f"private memory (`{profile.get('memory_file')}`)"
                badges.append(f"> 🧠 **{name} updated {mem_desc}:** {fact}")

        clean_text = text
        for p in cls.PATTERNS.values():
            clean_text = p.sub("", clean_text).strip()

        return clean_text, badges
