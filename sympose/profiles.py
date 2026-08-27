"""
Dynamic Profile, Soul & Tiered Memory Manager for Sympose.
"""

import os, sys, glob, re, datetime
from typing import Dict, List, Optional, Any
import yaml

from sympose.skills import skill_manager


class ProfileManager:
    """Dynamically loads agent profiles, souls, universal user cards, and tiered memory pools."""

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.reload_profiles()

    def bootstrap_missing_artifacts(self, profile: Dict[str, Any]) -> None:
        """Generates soul, memory, universal user card, and shared team memory from .example templates if absent."""
        handle, name, title = profile.get("handle", "agent").lower(), profile.get("name", "Agent"), profile.get("title", "Specialist Advisor")
        os.makedirs(self.profiles_dir, exist_ok=True)
        for path, default_content in [
            (os.path.join(self.profiles_dir, "user_profile.md"), "# Universal User Profile\n\n- **Primary User**: user\n- **Environment**: macOS / Linux\n"),
            (os.path.join(self.profiles_dir, "_shared_memory.md"), "# Shared Team Working Memory\n\n- **Active Project**: Sympose Agent Hub\n"),
            (profile.get("soul_file") or os.path.join(self.profiles_dir, f"{handle}_soul.md"), f"# {name}: Core Directives\n\nYou are **{name}**, the {title} in Sympose.\n"),
            (profile.get("memory_file") or os.path.join(self.profiles_dir, f"{handle}_memory.md"), f"# {name}: Working Memory\n\n- **Role**: {title}\n")
        ]:
            if not os.path.exists(path):
                content = default_content
                ex_path = f"{path}.example"
                if os.path.exists(ex_path):
                    try:
                        with open(ex_path, "r", encoding="utf-8") as ef: content = ef.read()
                    except Exception: pass
                try:
                    with open(path, "w", encoding="utf-8") as f: f.write(content)
                except Exception: pass

        profile["soul_file"] = profile.get("soul_file") or os.path.join(self.profiles_dir, f"{handle}_soul.md")
        profile["memory_file"] = profile.get("memory_file") or os.path.join(self.profiles_dir, f"{handle}_memory.md")
        if not profile.get("thinking_phrases"):
            profile["thinking_phrases"] = [f"Consulting {name}...", "Distilling insights...", "Formulating plan..."]

    def reload_profiles(self) -> Dict[str, Dict[str, Any]]:
        self.profiles.clear()
        if not os.path.exists(self.profiles_dir):
            return self.profiles

        for filepath in glob.glob(os.path.join(self.profiles_dir, "*.yaml")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "handle" in data:
                        self.bootstrap_missing_artifacts(data)
                        self.profiles[data["handle"].lower()] = data
            except Exception as e:
                print(f"⚠️ Error loading profile {filepath}: {e}", file=sys.stderr)
        return self.profiles

    def get_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        return self.profiles.get(handle.lower())

    def list_personas(self) -> List[Dict[str, Any]]:
        self.reload_profiles()
        return list(self.profiles.values())

    def _read_file_safe(self, path: Optional[str]) -> str:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return ""
        return ""

    def build_system_prompt(self, profile: Dict[str, Any]) -> str:
        handle, name = profile.get("handle", "agent"), profile.get("name", profile.get("handle", "agent"))
        user_card = self._read_file_safe(os.path.join(self.profiles_dir, "user_profile.md"))
        m = re.search(r"[-*]?\s*(?:\*\*|__)?(?:Primary\s+User|User|Name)(?:\*\*|__)?\s*:\s*([^\n\r]+)", user_card, re.I)
        primary_user = m.group(1).strip().strip("*_`") if m and m.group(1).strip() else (os.getenv("USER") or "User")

        v_folders = profile.get("vault_folders") or [profile.get("vault_folder", "General")]
        vf_desc = "Root Vault (All Folders)" if ("" in v_folders or "*" in v_folders) else ", ".join(f"`{f}/`" for f in v_folders)
        is_shared = profile.get("share_memory", False)
        sharing_desc = "Shared Team Pool (`_shared_memory.md`)" if is_shared else "Air-Gapped Private Memory"
        mv = os.getenv("MASTER_VAULT_PATH", "Local Workspace")
        sources = f"Core User Profile, {'Shared Team Working Memory, ' if is_shared else ''}Persona Working Memory, and Allowed Obsidian Vault Folders ({vf_desc})"

        prompt_parts: List[str] = []
        soul_txt = self._read_file_safe(profile.get("soul_file"))
        if soul_txt:
            prompt_parts.append(soul_txt.replace("{{user}}", primary_user).replace("{{handle}}", handle).replace("{{name}}", name))

        if user_card:
            prompt_parts.append(f"### Core User Profile & Identity:\n{user_card}")

        if is_shared and (shared_mem := self._read_file_safe(os.path.join(self.profiles_dir, "_shared_memory.md"))):
            prompt_parts.append(f"### Shared Team Working Memory:\n{shared_mem}")

        if persona_mem := self._read_file_safe(profile.get("memory_file")):
            prompt_parts.append(f"### Persona Working Memory:\n{persona_mem}")

        rules_txt = self._read_file_safe(os.path.join("prompts", "workspace_rules.md")) or self._read_file_safe("workspace_rules.md")
        if rules_txt:
            rules_formatted = (
                rules_txt.replace("{{workspace_root}}", os.getcwd())
                .replace("{{master_vault_path}}", mv)
                .replace("{{sandboxed_vault}}", vf_desc)
                .replace("{{memory_mode}}", f"{sharing_desc} (File: `{profile.get('memory_file')}`)")
                .replace("{{current_datetime}}", datetime.datetime.now().strftime("%Y-%m-%d %A %H:%M"))
                .replace("{{sources}}", sources)
                .replace("{{user}}", primary_user)
                .replace("{{handle}}", handle)
                .replace("{{name}}", name)
            )
            prompt_parts.append(rules_formatted)

        if active_skills := profile.get("skills", []):
            if isinstance(active_skills, list) and (skills_txt := skill_manager.format_skills_for_prompt(active_skills)):
                prompt_parts.append(skills_txt)

        peers = [f"- @{p['handle']}: {p.get('name', p['handle'])} ({p.get('title', 'Specialist')})" for p in self.profiles.values() if p["handle"] != profile["handle"]]
        if peers: prompt_parts.append("### Available Specialist Peers in Sympose:\n" + "\n".join(peers))

        return "\n\n".join(prompt_parts)

    def _append_to_file(self, file_path: str, fact: str) -> bool:
        try:
            from sympose.compactor import get_file_lock
            lock = get_file_lock(file_path)
            with lock:
                os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
                existing = self._read_file_safe(file_path).lower()
                lines = [l.strip() for l in fact.strip().split("\n") if l.strip()]
                new_lines = []
                for l in lines:
                    clean = l[2:].strip() if (l.startswith("- ") or l.startswith("* ")) else l
                    if clean.lower() not in existing:
                        new_lines.append(f"- {clean}")
                if new_lines:
                    with open(file_path, "a", encoding="utf-8") as f:
                        f.write("\n" + "\n".join(new_lines))
                return True
        except Exception:
            return False

    def append_memory(self, handle: str, fact: str, force_shared: Optional[bool] = None) -> bool:
        """Appends facts to persona memory and optionally shared memory if share_memory is active."""
        profile = self.get_profile(handle)
        if not profile:
            return False

        is_shared = profile.get("share_memory", False) if force_shared is None else force_shared
        mem_file = profile.get("memory_file", f"profiles/{handle}_memory.md")
        ok = self._append_to_file(mem_file, fact)

        try:
            from sympose.compactor import MemoryCompactor
            MemoryCompactor.check_and_compact_async(mem_file, is_shared=False)
        except Exception:
            pass

        if is_shared:
            shared_file = os.path.join(self.profiles_dir, "_shared_memory.md")
            self._append_to_file(shared_file, fact)
            try:
                from sympose.compactor import MemoryCompactor
                MemoryCompactor.check_and_compact_async(shared_file, is_shared=True)
            except Exception:
                pass

        return ok
