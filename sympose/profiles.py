"""
Dynamic Profile, Soul & Tiered Memory Manager for Sympose.
"""

import os
import sys
import glob
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
        """Generates soul, memory, universal user card, and shared team memory if absent."""
        handle, name, title = profile.get("handle", "agent").lower(), profile.get("name", "Agent"), profile.get("title", "Specialist Advisor")
        os.makedirs(self.profiles_dir, exist_ok=True)
        for path, content in [
            (os.path.join(self.profiles_dir, "user_profile.md"), "# Universal User Profile\n\n- **Primary User**: damiro\n- **Environment**: macOS\n"),
            (os.path.join(self.profiles_dir, "_shared_memory.md"), "# Shared Team Working Memory\n\n- **Active Project**: Sympose Agent Hub\n"),
            (profile.get("soul_file") or os.path.join(self.profiles_dir, f"{handle}_soul.md"), f"# {name}: Core Directives\n\nYou are **{name}**, the {title} in Sympose.\n"),
            (profile.get("memory_file") or os.path.join(self.profiles_dir, f"{handle}_memory.md"), f"# {name}: Working Memory\n\n- **Role**: {title}\n")
        ]:
            if not os.path.exists(path):
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

        # 4. Specialized Skills (Modular Playbooks from skills/)
        active_skills = profile.get("skills", [])
        if isinstance(active_skills, list) and active_skills:
            skills_txt = skill_manager.format_skills_for_prompt(active_skills)
            if skills_txt:
                prompt_parts.append(skills_txt)

        v_folders = profile.get("vault_folders") or [profile.get("vault_folder", "General")]
        vf_desc = "Root Vault (All Folders)" if ("" in v_folders or "*" in v_folders) else ", ".join(f"`{f}/`" for f in v_folders)
        mf = profile.get("memory_file", f"profiles/{profile.get('handle')}_memory.md")
        is_shared = profile.get("share_memory", False)
        sharing_desc = "Shared Team Pool (`_shared_memory.md`)" if is_shared else "Air-Gapped Private Memory"

        mv = os.getenv("MASTER_VAULT_PATH", "Local Workspace")
        sources = f"Core User Profile, {'Shared Team Working Memory, ' if is_shared else ''}Persona Working Memory, and your Allowed Obsidian Vault Folders ({vf_desc})"
        prompt_parts.append(
            f"### Runtime Environment & Spatial Coordinates:\n"
            f"You are operating within Sympose Agent Hub on macOS.\n"
            f"- App Workspace Root: `{os.getcwd()}`\n"
            f"- Master Obsidian Vault: `{mv}` (configured via `MASTER_VAULT_PATH` in `.env`)\n"
            f"- Sandboxed Vault Access: {vf_desc}\n"
            f"- Memory Mode: {sharing_desc} (File: `{mf}`, Shared Pool: `profiles/_shared_memory.md`)\n\n"
            f"### Strict Memory Grounding & Anti-Hallucination:\n"
            f"1. ASSUME INTERRUPTION: Your context window is bounded and might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory. Proactively checkpoint architectural decisions, milestone progress, and user facts using `[REMEMBER: <fact>]` or `[WRITE_NOTE: <filename> | <content>]`.\n"
            f"2. Your only knowledge of user history, plans, and past agreements comes strictly from {sources}, and active turns.\n"
            f"3. ZERO TOLERANCE FOR FABRICATION: When asked about past user facts, decisions, or agreements not in your memory, vault context, or active turns, never guess or fabricate. Candidly state that you don't have that recorded.\n"
            f"4. UNRECOGNIZED / GARBLED INPUT: If user input contains accidental terminal escape noise (e.g. `^[^[`), gibberish, or unclear typos, respond with a natural clarification (e.g. 'Looks like some terminal noise or a typo—what can I help you with?') rather than assuming it is a forgotten memory.\n"
            f"5. ZERO TIME-DELAY SIMULATION: You process requests immediately in the current turn. You do NOT have background execution threads across minutes or hours. NEVER say 'Give me a few minutes', 'I will look into this and come back', 'hang tight', or 'Give me a moment to process'. Always deliver your findings immediately in the current turn or state what specific information is missing.\n\n"
            f"### Autonomic Action Protocols:\n"
            f"- Working Memory: `[REMEMBER: <fact>]` saves bullet points to working memory.\n"
            f"- Create Note: `[WRITE_NOTE: <filename.md> | <content>]` creates/overwrites notes in allowed vault folders.\n"
            f"- Append Note: `[APPEND_NOTE: <filename.md> | <content>]` appends content to notes in allowed vault folders.\n"
            f"- Daily Note: `[DAILY_NOTE: <reflection>]` appends to `Daily Notes/YYYY-MM-DD.md`.\n"
            f"- Sub-Agent Worker: `[SPAWN_WORKER: <skill_or_mcp> | <task_instructions>]` delegates isolated tasks (running shell/git commands, inspecting files, executing MCP tools) to an ephemeral sub-agent.\n"
            f"- Runtime Configuration: `[CONFIG_SET: <key> | <value>]` updates and persists settings in `config.yaml` (e.g. `performance.request_timeout`, `performance.max_context_turns`, `performance.max_worker_tool_turns`, `session.exit_behavior.auto_save`). Use this when the user asks you to adjust runtime settings.\n"
            f"- Create Agent Persona: `[CREATE_PERSONA: <handle> | <yaml_manifest_content>]` creates a new specialist agent in the ecosystem. Automatically writes `profiles/<handle>.yaml`, bootstraps soul and memory, and registers @<handle> immediately for `/switch`.\n"
            f"- Retire / Delete Agent Persona: `[DELETE_PERSONA: <handle>]` safely retires an agent by moving their profile files to `profiles/_archived/<handle>/`.\n\n"
            f"### CRITICAL ACTION EXECUTION RULES:\n"
            f"1. NEVER mock, type out, or simulate `> 🛠️ **Sub-Agent Worker Report**` or fake command results in your message text.\n"
            f"2. You MUST emit the literal bracketed tag `[SPAWN_WORKER: <skill_or_mcp> | <task>]`. The Sympose runtime will execute real local tools and inject the ground-truth report automatically.\n"
            f"3. The runtime executes these tags atomically upon stream completion and confirms them to the user.\n"
            f"4. DOMAIN SANDBOX BOUNDARIES: Your vault access is strictly sandboxed to {vf_desc}. For instance, private personal reflections in `Daily/` are strictly air-gapped for @aurelius. If the user asks for notes in folders outside your sandbox, DO NOT attempt to access them or spawn a worker to bypass your boundary. Politely state that the folder is outside your sandbox and suggest switching to the authorized specialist (e.g. `/switch @aurelius`).\n"
            f"5. DIRECT IN-TURN ANSWERING: If the requested notes or answers are already present in your pre-turn context (`### Vault Search Results` or `### Sandboxed Vault Note`), DO NOT spawn a worker (`[SPAWN_WORKER]`). Answer the user immediately in-turn (<1.0s) without redundant sub-agent delegation."
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
