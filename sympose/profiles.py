"""
Dynamic Profile, Soul & Tiered Memory Manager for Sympose.
"""

import os, sys, glob, re, datetime, logging
from typing import Dict, List, Optional, Any, Tuple
import yaml

log = logging.getLogger(__name__)

from sympose.skills import skill_manager
from sympose.config import DEFAULT_CHAT_MODEL


class ProfileManager:
    """Dynamically loads agent profiles, souls, universal user cards, and tiered memory pools."""

    def __init__(self, profiles_dir: Optional[str] = None):
        if profiles_dir:
            self.profiles_dir = os.path.abspath(profiles_dir)
        else:
            from sympose.bootstrap import resolve_workspace_dir
            self.profiles_dir = os.path.abspath(os.path.join(resolve_workspace_dir(), "profiles"))
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._profiles_mtime: float = 0.0
        # mtime-keyed cache for _read_file_safe — build_system_prompt re-reads the
        # soul, user card, shared/persona memory, and workspace rules every turn;
        # this skips the disk read when the resolved file hasn't changed.
        self._file_cache: Dict[str, Tuple[float, str]] = {}
        self.reload_profiles()

    def update_persona_skills(self, handle: str, skill_name: str, action: str = "add") -> Tuple[bool, str]:
        """Adds or removes a skill from a persona's YAML manifest and reloads profiles."""
        h = handle.lower().replace("@", "").strip()
        yaml_file = os.path.join(self.profiles_dir, f"{h}.yaml")
        if not os.path.exists(yaml_file):
            return False, f"Profile manifest `{yaml_file}` not found."

        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return False, f"Invalid YAML structure in `{yaml_file}`."

            current_skills = list(data.get("skills") or [])
            norm_skill = skill_name.strip().lower()

            if action in ("add", "mount", "install"):
                if norm_skill in current_skills:
                    return True, f"Skill `{norm_skill}` is already equipped on `@{h}`."
                current_skills.append(norm_skill)
                data["skills"] = current_skills
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                self.reload_profiles()
                p_name = data.get("name", h)
                return True, f"Mounted skill `{norm_skill}` to {p_name} (`@{h}`)."

            elif action in ("remove", "unmount", "uninstall", "rm"):
                if norm_skill not in current_skills:
                    return False, f"Skill `{norm_skill}` is not mounted on `@{h}`."
                current_skills.remove(norm_skill)
                data["skills"] = current_skills
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                self.reload_profiles()
                p_name = data.get("name", h)
                return True, f"Unmounted skill `{norm_skill}` from {p_name} (`@{h}`)."

            return False, f"Unknown action `{action}` (use 'add' or 'remove')."
        except Exception as e:
            return False, f"Failed to update `{yaml_file}`: {e}"

    def bootstrap_missing_artifacts(self, profile: Dict[str, Any]) -> None:
        """Generates soul, memory, universal user card, and shared team memory from .example templates if absent."""
        handle, name, title = profile.get("handle", "agent").lower(), profile.get("name", "Agent"), profile.get("title", "Specialist Advisor")
        os.makedirs(self.profiles_dir, exist_ok=True)
        soul_name = os.path.basename(profile.get("soul_file") or f"{handle}_soul.md")
        mem_name = os.path.basename(profile.get("memory_file") or f"{handle}_memory.md")
        soul_path = os.path.join(self.profiles_dir, soul_name)
        mem_path = os.path.join(self.profiles_dir, mem_name)

        # Fallback only — CREATE_PERSONA writes a real soul directly from its
        # manifest's `soul_content` field when the model provides one; this
        # generic scaffold is what a persona gets if it doesn't (e.g. a
        # hand-dropped 4-line YAML manifest, per creating-agents.md's "Quick
        # Genesis" path). Still generic — it can't know what a "Grace Hopper"
        # or "Dieter Rams" reference means — but it at least carries the same
        # anti-hallucination and action-awareness floor every other agent gets,
        # instead of one bare sentence.
        fallback_soul = (
            f"# {name}: Core Directives\n\n"
            f"You are **{name}**, the {title} in Sympose.\n\n"
            "### Core Directives:\n"
            "- Think from first principles; keep responses concise, structured, and actionable.\n"
            "- Proactively checkpoint durable facts and decisions with `[REMEMBER: <fact>]` or `[WRITE_NOTE: <path> | <content>]` — your context window is bounded and may reset.\n"
            "- **Strict Anti-Hallucination**: if asked about a person, fact, or note not present in your memory, profile, or vault context, say so plainly rather than inventing an answer.\n"
        )

        for path, default_content in [
            (os.path.join(self.profiles_dir, "user_profile.md"), "# Universal User Profile\n\n- **Primary User**: user\n- **Environment**: macOS / Linux\n"),
            (os.path.join(self.profiles_dir, "_shared_memory.md"), "# Shared Team Working Memory\n\n- **Active Project**: Sympose Agent Hub\n"),
            (soul_path, fallback_soul),
            (mem_path, f"# {name}: Working Memory\n\n- **Role**: {title}\n")
        ]:
            if not os.path.exists(path):
                content = default_content
                ex_path = f"{path}.example"
                if os.path.exists(ex_path):
                    try:
                        with open(ex_path, "r", encoding="utf-8") as ef: content = ef.read()
                    except Exception as e: log.debug("[scaffold] failed to read template %s: %s", ex_path, e)
                try:
                    with open(path, "w", encoding="utf-8") as f: f.write(content)
                except Exception as e: log.debug("[scaffold] failed to write %s: %s", path, e)

        profile["soul_file"] = soul_path
        profile["memory_file"] = mem_path
        if not profile.get("model"):
            profile["model"] = DEFAULT_CHAT_MODEL
        if "skills" not in profile or profile.get("skills") is None:
            profile["skills"] = []
        if not profile.get("thinking_phrases"):
            profile["thinking_phrases"] = [f"Consulting {name}...", "Distilling insights...", "Formulating plan..."]

    DEFAULT_STARTER_PROFILES: Dict[str, Dict[str, Any]] = {
        "samantha": {
            "name": "Samantha",
            "handle": "samantha",
            "title": "Polymath Strategic Master Orchestrator",
            "model": DEFAULT_CHAT_MODEL,
            "icon_emoji": ":brain:",
            "vault_folders": ["General", "Projects", "Thoughts", "Templates"],
            "share_memory": True,
            "skills": ["sympose_mastery", "strategic_analysis", "vault_recall", "vault_write", "web_search"],
            "thinking_phrases": ["Connecting high-level dots...", "Synthesizing strategic options...", "Distilling signal from noise..."]
        }
    }

    def reload_profiles(self) -> Dict[str, Dict[str, Any]]:
        self.profiles.clear()
        os.makedirs(self.profiles_dir, exist_ok=True)
        yaml_files = glob.glob(os.path.join(self.profiles_dir, "*.yaml"))

        # Auto-seed starter profiles if directory is empty
        if not yaml_files:
            for h, pdata in self.DEFAULT_STARTER_PROFILES.items():
                p_file = os.path.join(self.profiles_dir, f"{h}.yaml")
                try:
                    with open(p_file, "w", encoding="utf-8") as f:
                        yaml.dump(pdata, f, default_flow_style=False)
                except Exception:
                    pass
            yaml_files = glob.glob(os.path.join(self.profiles_dir, "*.yaml"))

        for filepath in yaml_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "handle" in data:
                        self.bootstrap_missing_artifacts(data)
                        self.profiles[data["handle"].lower()] = data
            except Exception as e:
                log.warning("Error loading profile %s: %s", filepath, e)
        # Record mtime so list_personas() can skip redundant reloads
        try:
            self._profiles_mtime = os.path.getmtime(self.profiles_dir)
        except OSError:
            self._profiles_mtime = 0.0
        return self.profiles

    def get_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        return self.profiles.get(handle.lower())

    def list_personas(self) -> List[Dict[str, Any]]:
        """Returns all loaded personas, reloading from disk only when the profiles directory has changed."""
        try:
            current_mtime = os.path.getmtime(self.profiles_dir)
        except OSError:
            current_mtime = 0.0
        if current_mtime != self._profiles_mtime:
            self.reload_profiles()
        return list(self.profiles.values())

    def _read_file_safe(self, path: Optional[str]) -> str:
        if not path:
            return ""
        # Try direct path
        candidates = [
            path,
            os.path.join(self.profiles_dir, path),
            os.path.join(self.profiles_dir, os.path.basename(path)),
            os.path.join(os.path.dirname(self.profiles_dir), path),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isfile(c):
                try:
                    current_mtime = os.path.getmtime(c)
                    cached = self._file_cache.get(c)
                    if cached and cached[0] == current_mtime:
                        return cached[1]
                    with open(c, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    self._file_cache[c] = (current_mtime, content)
                    return content
                except Exception:
                    pass
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

        workspace_parent = os.path.dirname(os.path.abspath(self.profiles_dir))
        rules_txt = (
            self._read_file_safe(os.path.join(workspace_parent, "prompts", "workspace_rules.md"))
            or "### Directives:\n- Think systematically and provide crisp analysis.\n- Save durable insights to memory."
        )
        rules_formatted = (
            rules_txt.replace("{{workspace_root}}", workspace_parent)
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
