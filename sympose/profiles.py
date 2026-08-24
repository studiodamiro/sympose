"""
Dynamic Profile & Soul Manager for Sympose.
"""

import os
import sys
import glob
from typing import Dict, List, Optional, Any
import yaml


class ProfileManager:
    """Dynamically loads and manages YAML agent profiles, souls, and memories."""

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.reload_profiles()

    def reload_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Scans profiles_dir and loads all valid *.yaml configurations."""
        self.profiles.clear()
        if not os.path.exists(self.profiles_dir):
            return self.profiles

        for filepath in glob.glob(os.path.join(self.profiles_dir, "*.yaml")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "handle" in data:
                        handle = data["handle"].lower()
                        self.profiles[handle] = data
            except Exception as e:
                print(f"⚠️ Error loading profile {filepath}: {e}", file=sys.stderr)

        return self.profiles

    def get_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        """Retrieves a loaded profile by handle."""
        return self.profiles.get(handle.lower())

    def list_personas(self) -> List[Dict[str, Any]]:
        """Returns a list of all active persona configurations."""
        return list(self.profiles.values())

    def build_system_prompt(self, profile: Dict[str, Any]) -> str:
        """Constructs the composite system prompt from soul, memory, and rules."""
        prompt_parts = []

        # 1. Soul directives
        soul_file = profile.get("soul_file")
        if soul_file and os.path.exists(soul_file):
            try:
                with open(soul_file, "r", encoding="utf-8") as f:
                    prompt_parts.append(f.read().strip())
            except Exception as e:
                prompt_parts.append(f"Soul Error: Unable to read {soul_file}: {e}")

        # 2. Persistent working memory
        memory_file = profile.get("memory_file")
        if memory_file and os.path.exists(memory_file):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    mem_content = f.read().strip()
                    if mem_content:
                        prompt_parts.append(f"### Persistent Working Memory:\n{mem_content}")
            except Exception as e:
                prompt_parts.append(f"Memory Error: Unable to read {memory_file}: {e}")

        # 3. Global workspace rules (if present)
        if os.path.exists("workspace_rules.md"):
            try:
                with open("workspace_rules.md", "r", encoding="utf-8") as f:
                    rules_content = f.read().strip()
                    if rules_content:
                        prompt_parts.append(f"### Global Workspace Rules:\n{rules_content}")
            except Exception:
                pass

        # 4. Runtime Capabilities & Tool Awareness
        vault_folder = profile.get("vault_folder", "General")
        prompt_parts.append(
            f"### Runtime Environment & Capabilities:\n"
            f"You are operating within the Sympose Agent Hub on macOS.\n"
            f"- Sandboxed Vault: You can read/write notes in your assigned domain `{vault_folder}/`.\n"
            f"- Commands available in this session:\n"
            f"  * `/note <filename.md> <content>`: Create or append to a Markdown file in `{vault_folder}/`.\n"
            f"  * `/daily <reflection>`: Append a timestamped reflection to `Daily Notes/YYYY-MM-DD.md`.\n"
            f"  * `/vault <query>`: Search your sandboxed domain notes.\n"
            f"  * `/remember <fact>`: Save facts into your persistent memory.\n"
            f"  * `/ask <@peer> <task>`: Delegate a task to an isolated peer agent."
        )

        # 5. Context awareness of peer personas (for delegation)
        other_agents = [
            f"- @{p['handle']}: {p.get('name', p['handle'])} ({p.get('title', 'Specialist')})"
            for p in self.profiles.values()
            if p["handle"] != profile["handle"]
        ]
        if other_agents:
            prompt_parts.append("### Available Specialist Peers in Sympose:\n" + "\n".join(other_agents))

        return "\n\n".join(prompt_parts)

    def append_memory(self, handle: str, fact: str) -> bool:
        """Appends a new fact to the persona's _memory.md file."""
        profile = self.get_profile(handle)
        if not profile:
            return False

        memory_file = profile.get("memory_file")
        if not memory_file:
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(memory_file)), exist_ok=True)
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(f"\n- {fact.strip()}")
            return True
        except Exception as e:
            print(f"⚠️ Failed to write memory to {memory_file}: {e}", file=sys.stderr)
            return False
