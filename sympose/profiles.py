"""
Dynamic Profile, Soul & Tiered Memory Manager for Sympose.
"""

import os
import sys
import glob
from typing import Dict, List, Optional, Any
import yaml


class ProfileManager:
    """Dynamically loads agent profiles, souls, universal user cards, and tiered memory pools."""

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.reload_profiles()

    def bootstrap_missing_artifacts(self, profile: Dict[str, Any]) -> None:
        """Generates soul, memory, universal user card, and shared team memory if absent."""
        handle = profile.get("handle", "agent").lower()
        name = profile.get("name", handle.capitalize())
        title = profile.get("title", "Specialist Advisor")

        # 1. Bootstrap Universal User Profile if absent
        user_file = os.path.join(self.profiles_dir, "user_profile.md")
        if not os.path.exists(user_file):
            try:
                os.makedirs(self.profiles_dir, exist_ok=True)
                with open(user_file, "w", encoding="utf-8") as f:
                    f.write("# Universal User Profile\n\n- **Primary User**: damiro\n- **Environment**: macOS\n")
            except Exception:
                pass

        # 2. Bootstrap Shared Team Memory if absent
        shared_file = os.path.join(self.profiles_dir, "_shared_memory.md")
        if not os.path.exists(shared_file):
            try:
                with open(shared_file, "w", encoding="utf-8") as f:
                    f.write("# Shared Team Working Memory\n\n- **Active Project**: Sympose Agent Hub\n")
            except Exception:
                pass

        # 3. Bootstrap Soul
        soul_file = profile.get("soul_file") or os.path.join(self.profiles_dir, f"{handle}_soul.md")
        profile["soul_file"] = soul_file
        if not os.path.exists(soul_file):
            try:
                with open(soul_file, "w", encoding="utf-8") as f:
                    f.write(f"# {name}: Core Directives\n\nYou are **{name}**, the {title} in Sympose.\n")
            except Exception:
                pass

        # 4. Bootstrap Memory
        memory_file = profile.get("memory_file") or os.path.join(self.profiles_dir, f"{handle}_memory.md")
        profile["memory_file"] = memory_file
        if not os.path.exists(memory_file):
            try:
                with open(memory_file, "w", encoding="utf-8") as f:
                    f.write(f"# {name}: Working Memory\n\n- **Role**: {title}\n")
            except Exception:
                pass

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
        prompt_parts = []
        soul_txt = self._read_file_safe(profile.get("soul_file"))
        if soul_txt:
            prompt_parts.append(soul_txt)

        # 1. Universal User Profile (Read by ALL agents)
        user_card = self._read_file_safe(os.path.join(self.profiles_dir, "user_profile.md"))
        if user_card:
            prompt_parts.append(f"### Core User Profile & Identity:\n{user_card}")

        # 2. Shared Team Memory (Read only by agents with share_memory: true)
        if profile.get("share_memory", False):
            shared_mem = self._read_file_safe(os.path.join(self.profiles_dir, "_shared_memory.md"))
            if shared_mem:
                prompt_parts.append(f"### Shared Team Working Memory:\n{shared_mem}")

        # 3. Persona-Specific Working Memory
        persona_mem = self._read_file_safe(profile.get("memory_file"))
        if persona_mem:
            prompt_parts.append(f"### Persona Working Memory:\n{persona_mem}")

        rules_txt = self._read_file_safe("workspace_rules.md")
        if rules_txt:
            prompt_parts.append(f"### Global Workspace Rules:\n{rules_txt}")

        v_folders = profile.get("vault_folders") or [profile.get("vault_folder", "General")]
        vf_desc = "Root Vault (All Folders)" if ("" in v_folders or "*" in v_folders) else ", ".join(f"`{f}/`" for f in v_folders)
        mf = profile.get("memory_file", f"profiles/{profile.get('handle')}_memory.md")
        is_shared = profile.get("share_memory", False)
        sharing_desc = "Shared Team Pool (`_shared_memory.md`)" if is_shared else "Air-Gapped Private Memory"

        sources = "Core User Profile, Shared Team Working Memory, Persona Working Memory" if is_shared else "Core User Profile, Persona Working Memory"
        prompt_parts.append(
            f"### Runtime Environment & Capabilities:\n"
            f"You are operating within Sympose Agent Hub on macOS.\n"
            f"- Sandboxed Vault: Read/write access to {vf_desc}.\n"
            f"- Memory Mode: {sharing_desc} (File: `{mf}`).\n\n"
            f"### Strict Memory Grounding & Anti-Hallucination:\n"
            f"1. Your only knowledge of user history, plans, and past agreements comes strictly from {sources}, and active turns.\n"
            f"2. ZERO TOLERANCE FOR FABRICATION: If the user asks about a detail not explicitly in your memory or context, NEVER guess. State: 'I don't have that recorded in my memory. What was it so I can log it for you?'\n\n"
            f"### Autonomic Action Protocols:\n"
            f"- Working Memory: `[REMEMBER: <fact>]` saves bullet points to working memory.\n"
            f"- Create Note: `[WRITE_NOTE: <filename.md> | <content>]` creates/overwrites notes in allowed vault folders.\n"
            f"- Append Note: `[APPEND_NOTE: <filename.md> | <content>]` appends content to notes in allowed vault folders.\n"
            f"- Daily Note: `[DAILY_NOTE: <reflection>]` appends to `Daily Notes/YYYY-MM-DD.md`.\n"
            f"The runtime executes these tags atomically upon stream completion and confirms them to the user."
        )

        peers = [f"- @{p['handle']}: {p.get('name', p['handle'])} ({p.get('title', 'Specialist')})"
                 for p in self.profiles.values() if p["handle"] != profile["handle"]]
        if peers:
            prompt_parts.append("### Available Specialist Peers in Sympose:\n" + "\n".join(peers))

        return "\n\n".join(prompt_parts)

    def _append_to_file(self, file_path: str, fact: str) -> bool:
        try:
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
        ok = self._append_to_file(profile.get("memory_file", f"profiles/{handle}_memory.md"), fact)
        if is_shared:
            self._append_to_file(os.path.join(self.profiles_dir, "_shared_memory.md"), fact)
        return ok
