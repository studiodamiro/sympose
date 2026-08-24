"""
Dynamic Profile & Soul Manager for Sympose.
"""

import os
import sys
import glob
from typing import Dict, List, Optional, Any
import yaml


class ProfileManager:
    """Dynamically loads, bootstraps, and manages YAML agent profiles, souls, and memories."""

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.reload_profiles()

    def bootstrap_missing_artifacts(self, profile: Dict[str, Any]) -> None:
        """Autonomously generates _soul.md, _memory.md, and thinking_phrases if missing."""
        handle = profile.get("handle", "agent").lower()
        name = profile.get("name", handle.capitalize())
        title = profile.get("title", "Specialist Advisor")

        # 1. Bootstrap Soul file if absent
        soul_file = profile.get("soul_file") or os.path.join(self.profiles_dir, f"{handle}_soul.md")
        profile["soul_file"] = soul_file
        if not os.path.exists(soul_file):
            try:
                os.makedirs(os.path.dirname(os.path.abspath(soul_file)), exist_ok=True)
                default_soul = (
                    f"# {name}: Core Directives & Soul\n\n"
                    f"You are **{name}**, the {title} in Sympose.\n\n"
                    f"## Core Tone & Demeanor\n"
                    f"- **Domain Authority**: Provide rigorous, structured, and insightful guidance.\n"
                    f"- **High Signal, Zero Bloat**: Focus on actionable solutions, eliminate fluff, and challenge assumptions constructively.\n"
                    f"- **Collaborative Execution**: Formulate clear plans, verify constraints, and deliver surgical recommendations.\n"
                )
                with open(soul_file, "w", encoding="utf-8") as f:
                    f.write(default_soul)
            except Exception as e:
                print(f"⚠️ Failed to auto-generate soul for {handle}: {e}", file=sys.stderr)

        # 2. Bootstrap Memory file if absent
        memory_file = profile.get("memory_file") or os.path.join(self.profiles_dir, f"{handle}_memory.md")
        profile["memory_file"] = memory_file
        if not os.path.exists(memory_file):
            try:
                os.makedirs(os.path.dirname(os.path.abspath(memory_file)), exist_ok=True)
                default_memory = (
                    f"# {name}: Persistent Working Memory\n\n"
                    f"- **Role**: {title}\n"
                    f"- **Workflow**: High signal, zero bloat, verify before completion.\n"
                )
                with open(memory_file, "w", encoding="utf-8") as f:
                    f.write(default_memory)
            except Exception as e:
                print(f"⚠️ Failed to auto-generate memory for {handle}: {e}", file=sys.stderr)

        # 3. Bootstrap default thinking phrases if omitted
        if "thinking_phrases" not in profile or not profile["thinking_phrases"]:
            profile["thinking_phrases"] = [
                f"Consulting {name}...",
                f"Synthesizing {title.lower()} insights...",
                "Distilling signal from noise...",
                "Formulating the solution...",
            ]

    def reload_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Scans profiles_dir, bootstraps missing artifacts, and loads all *.yaml configurations."""
        self.profiles.clear()
        if not os.path.exists(self.profiles_dir):
            return self.profiles

        for filepath in glob.glob(os.path.join(self.profiles_dir, "*.yaml")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "handle" in data:
                        handle = data["handle"].lower()
                        self.bootstrap_missing_artifacts(data)
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

        # 4. Runtime Capabilities & Autonomic Actions
        vault_folder = profile.get("vault_folder", "General")
        memory_file = profile.get("memory_file", f"profiles/{profile.get('handle')}_memory.md")
        prompt_parts.append(
            f"### Runtime Environment & Capabilities:\n"
            f"You are operating within the Sympose Agent Hub on macOS.\n"
            f"- Sandboxed Vault: You can read/write notes in your assigned domain `{vault_folder}/`.\n"
            f"- Working Memory: Your persistent memory is located in `{memory_file}`.\n\n"
            f"### Strict Memory Truthfulness & Anti-Hallucination Protocol:\n"
            f"1. Your only knowledge of user history, past plans, agreements, and preferences comes strictly from `### Persistent Working Memory:` and the active chat turns.\n"
            f"2. ZERO TOLERANCE FOR FABRICATION: If the user asks whether you remember a fact, plan, framework, date, or detail (e.g. 'do you remember what I need to study?'), and that fact is NOT explicitly recorded in your memory or recent context, you MUST NEVER guess, hallucinate, or pretend to remember.\n"
            f"3. In such cases, candidly and honestly state: 'I don't have that recorded in my memory. What was it so I can log it for you?'\n\n"
            f"### Autonomic Memory Action Protocol:\n"
            f"Whenever the user tells you to remember something, or you discover a permanent rule, constraint, or preference that must persist across future sessions, you MUST include this exact tag in your response:\n"
            f"`[REMEMBER: <concise bullet point of fact to persist>]`\n"
            f"The Sympose runtime automatically intercepts this tag, appends it to `{memory_file}`, and confirms it to the user.\n\n"
            f"### User Slash Commands:\n"
            f"  * `/note <filename.md> <content>`: Create or append to a Markdown file in `{vault_folder}/`.\n"
            f"  * `/daily <reflection>`: Append a timestamped reflection to `Daily Notes/YYYY-MM-DD.md`.\n"
            f"  * `/vault <query>`: Search your sandboxed domain notes.\n"
            f"  * `/save [memory|obsidian|both]`: Summarize and save session takeaways.\n"
            f"  * `/remember <fact>`: Explicitly save a fact to persistent memory.\n"
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
        """Appends new facts or bullet points to the persona's _memory.md file with deduplication."""
        profile = self.get_profile(handle)
        if not profile:
            return False

        memory_file = profile.get("memory_file")
        if not memory_file:
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(memory_file)), exist_ok=True)
            existing_content = ""
            if os.path.exists(memory_file):
                with open(memory_file, "r", encoding="utf-8") as f:
                    existing_content = f.read().lower()

            lines = [line.strip() for line in fact.strip().split("\n") if line.strip()]
            formatted_lines = []
            for l in lines:
                clean_txt = l[2:].strip() if (l.startswith("- ") or l.startswith("* ")) else l
                if clean_txt.lower() not in existing_content:
                    formatted_lines.append(f"- {clean_txt}")

            if formatted_lines:
                with open(memory_file, "a", encoding="utf-8") as f:
                    f.write("\n" + "\n".join(formatted_lines))
            return True
        except Exception as e:
            print(f"⚠️ Failed to write memory to {memory_file}: {e}", file=sys.stderr)
            return False
