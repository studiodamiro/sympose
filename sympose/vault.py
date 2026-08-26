"""
Sandboxed Vault & Markdown Note Manager for Sympose.
"""

import os, re, datetime
from typing import Dict, Any, Optional, List
from sympose.config import is_safe_path, config_manager


class VaultManager:
    """Manages sandboxed reading, writing, high-density manifests, and searching in Obsidian vaults."""

    @staticmethod
    def _get_master_vault() -> Optional[str]:
        mv = os.getenv("MASTER_VAULT_PATH")
        return os.path.abspath(os.path.expanduser(mv)) if mv else None

    @classmethod
    def get_allowed_dirs(cls, profile: Dict[str, Any]) -> List[str]:
        mv = cls._get_master_vault()
        if not mv: return []
        try:
            os.makedirs(mv, exist_ok=True)
            folders = profile.get("vault_folders") or [profile.get("vault_folder", "")]
            if "" in folders or "*" in folders or "all" in folders: return [mv]
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
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        if not note_name.endswith(".md"): note_name += ".md"

        direct_target = os.path.join(mv, note_name)
        for allowed in allowed_dirs:
            if is_safe_path(direct_target, allowed) and os.path.exists(direct_target):
                try:
                    with open(direct_target, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read().strip()
                except Exception as e:
                    return f"Error reading note `{note_name}`: {e}"

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
    def get_folder_digest(cls, profile: Dict[str, Any], folder_name: str, max_files: int = 50) -> str:
        """Extracts high-density 1-line metadata for all notes in a folder for comprehensive synthesis."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        target_dir = next((d for d in allowed_dirs if os.path.basename(d).lower() == folder_name.lower()), None)
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        if not target_dir or not os.path.exists(target_dir):
            return f"Folder `{folder_name}` not found in allowed vault directories."

        entries, raw_ignore = [], config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
            for fn in sorted(files):
                if fn.endswith((".md", ".markdown", ".txt")):
                    fp = os.path.join(root, fn)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            head = f.read(1000)
                        parts = []
                        for k in ("name", "title", "aka", "tags", "birthday", "created", "up", "author"):
                            m = re.search(rf"^{k}:\s*([^\n\r]+)", head, re.M | re.I)
                            if m and m.group(1).strip() and not m.group(1).strip().startswith(("-", "[")):
                                parts.append(f"{k.capitalize()}: {m.group(1).strip()}")
                            else:
                                sub = re.findall(rf"^{k}:(?:\s*\n)((?:\s+-\s+[^\n]+\n)+)", head, re.M | re.I)
                                if sub:
                                    items = [x.strip("- \t\n\"'") for x in sub[0].strip().split("\n")]
                                    parts.append(f"{k.capitalize()}: {', '.join(items)}")
                        fl = next((line.strip("# \t\r") for line in head.split("\n") if line.strip() and not line.startswith("---") and ":" not in line), "")
                        summary = " | ".join(parts) if parts else fl[:80]
                        entries.append(f"- `{fn}`: {summary}" if summary else f"- `{fn}`")
                    except Exception:
                        entries.append(f"- `{fn}`")
                if len(entries) >= max_files: break

        return f"### High-Density Folder Digest (`{folder_name}/` - {len(entries)} notes):\n" + "\n".join(entries) if entries else f"No notes found in `{folder_name}/`."

    @classmethod
    def search(cls, profile: Dict[str, Any], query: str, target_folder: Optional[str] = None) -> str:
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs: return "⚠️ Master notes directory not configured or access denied."
        search_dirs = [d for d in allowed_dirs if os.path.basename(d).lower() == target_folder.lower()] if target_folder else allowed_dirs
        search_dirs = search_dirs or allowed_dirs

        query_lower, title_matches, content_matches = query.lower(), [], []
        raw_ignore = config_manager.get("vault.ignore_folders") or [".obsidian", ".git", "Attachments", ".trash"]
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        try:
            for allowed in search_dirs:
                for root, dirs, files in os.walk(allowed):
                    dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                    for file in files:
                        if file.endswith((".md", ".markdown", ".txt")):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, mv)
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in file.lower() or query_lower in rel_path.lower():
                                    title_matches.append(f"**{rel_path}**:\n{content[:1200].strip()}")
                                elif query_lower in content.lower():
                                    content_matches.append(f"**{rel_path}** (Content match):\n{content[:1200].strip()}")
                            if len(title_matches) >= 5: break
                    if len(title_matches) >= 5: break
        except Exception as e:
            return f"Error searching vault: {e}"

        all_matches = (title_matches + content_matches)[:5]
        return "\n\n---\n\n".join(all_matches) if all_matches else f"No notes found matching `{query}` in allowed vault folders."

    @classmethod
    def write_note(cls, profile: Dict[str, Any], note_name: str, content: str) -> str:
        mv, allowed_dirs, primary_dir = cls._get_master_vault(), cls.get_allowed_dirs(profile), cls.get_primary_dir(profile)
        if not mv or not primary_dir: return "Warning: Master notes directory not configured or path denied."
        if not note_name.endswith(".md"): note_name += ".md"
        target_file = os.path.join(mv, note_name) if ("/" in note_name or "\\" in note_name) else os.path.join(primary_dir, note_name)
        if not any(is_safe_path(target_file, allowed) for allowed in allowed_dirs):
            return f"Security Error: Target path `{note_name}` is outside assigned sandbox."

        now = datetime.datetime.now()
        date_str, time_str, rel_display = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M"), os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            is_new = not os.path.exists(target_file)
            with open(target_file, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(f"---\nentry: {date_str}\ncreated: {time_str}\ntype: note\nproject: sympose\nauthor: {profile.get('name', 'sympose')}\n---\n\n# {os.path.splitext(os.path.basename(note_name))[0]}\n\n")
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
        daily_fmt = os.getenv("DAILY_NOTES_FORMAT", "Daily/%Y/%m-%B/%Y-%m-%d.md")
        return cls.write_note(profile, now.strftime(daily_fmt), f"\n### Reflection ({now.strftime('%H:%M')})\n{reflection}")

    @classmethod
    def write_session_note(cls, profile: Dict[str, Any], summary_md: str, subfolder: str = "Sessions", session_title: Optional[str] = None) -> str:
        primary_dir, mv = cls.get_primary_dir(profile), cls._get_master_vault()
        if not primary_dir or not mv: return "Warning: Master notes directory not configured or path denied."
        now, handle = datetime.datetime.now(), profile.get("handle", "agent").lower()
        title_slug = f"_{session_title.lower().replace(' ', '_')}" if session_title else ""
        target_dir = os.path.join(primary_dir, subfolder)
        target_file = os.path.join(target_dir, f"{now.strftime('%Y-%m-%d_%H%M')}_{handle}{title_slug}_session.md")
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(f"---\nentry: {now.strftime('%Y-%m-%d')}\ncreated: {now.strftime('%Y-%m-%d %H:%M')}\ntype: session-log\nproject: sympose\nauthor: {profile.get('name', handle)}\ntags:\n  - session/log\n  - sympose/{handle}\n---\n\n# Session Log: {profile.get('name', handle)} ({now.strftime('%Y-%m-%d %H:%M')})\n\n{summary_md.strip()}\n")
            return f"Saved session note to Obsidian: `{os.path.relpath(target_file, mv)}`"
        except Exception as e:
            return f"Error: Failed to write session note: {e}"
