"""
Autonomic Action Tag Processor for Sympose Agents.
"""

import os
import shutil
import re
from typing import Dict, Any, List, Tuple
from sympose.vault import VaultManager
from sympose.skills import skill_manager
from sympose.workers import WorkerEngine, WorkerTask
from sympose.mcp import mcp_registry
from sympose.config import config_manager


class ActionProcessor:
    """Parses, executes, and badges autonomic model action tags ([REMEMBER], [WRITE_NOTE], [CONFIG_SET], [CREATE_PERSONA], [DELETE_PERSONA], etc.)."""

    # Tag Regex Patterns
    PATTERNS = {
        "WRITE_NOTE": re.compile(r"\[(?:ACTION:)?WRITE_NOTE:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "APPEND_NOTE": re.compile(r"\[(?:ACTION:)?APPEND_NOTE:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "DAILY_NOTE": re.compile(r"\[(?:ACTION:)?DAILY_NOTE:\s*([\s\S]+?)\]", re.IGNORECASE),
        "REMEMBER": re.compile(r"\[(?:ACTION:)?REMEMBER:\s*([^\]]+?)\]", re.IGNORECASE),
        "SPAWN_WORKER": re.compile(r"\[(?:ACTION:)?SPAWN_WORKER:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "CONFIG_SET": re.compile(r"\[(?:ACTION:)?CONFIG_SET:\s*([^|\]]+?)\s*\|\s*([^\]]+?)\]", re.IGNORECASE),
        "CREATE_PERSONA": re.compile(r"\[(?:ACTION:)?CREATE_PERSONA:\s*([^|\]]+?)\s*\|\s*([\s\S]*?)\n\s*\]", re.IGNORECASE),
        "DELETE_PERSONA": re.compile(r"\[(?:ACTION:)?DELETE_PERSONA:\s*([^\]]+?)\]", re.IGNORECASE),
        "WRITE_CANVAS": re.compile(r"\[(?:ACTION:)?WRITE_CANVAS:\s*([^|\]]+?)\s*\|\s*([\s\S]+?)\]", re.IGNORECASE),
        "REACT": re.compile(r"\[(?:ACTION:)?REACT:\s*([a-zA-Z0-9_\-+:]+?)\]", re.IGNORECASE),
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

        # 5. SPAWN_WORKER Tags
        for match in cls.PATTERNS["SPAWN_WORKER"].finditer(text):
            spec = match.group(1).strip()
            task_prompt = match.group(2).strip()
            if task_prompt:
                # Parse spec which can be comma-separated skills or servers (e.g. "git_workflow,github")
                tokens = [t.strip() for t in spec.replace(";", ",").split(",") if t.strip()]
                skills_to_load = []
                mcp_to_load = []
                for tok in tokens:
                    if skill_manager.get_skill(tok):
                        skills_to_load.append(tok)
                    elif tok.lower() in mcp_registry.servers:
                        mcp_to_load.append(tok)
                    else:
                        skills_to_load.append(tok)

                task = WorkerTask(
                    task_prompt=task_prompt,
                    skills=skills_to_load,
                    mcp_servers=mcp_to_load,
                    parent_agent=handle,
                )
                worker_output_chunks = list(WorkerEngine.execute_worker_stream(task))
                worker_result = "".join(worker_output_chunks).strip()
                badge_spec = f"Skills: `{', '.join(skills_to_load)}`" if skills_to_load else f"MCP: `{', '.join(mcp_to_load)}`"
                badges.append(
                    f"\n> 🛠️ **Sub-Agent Worker Report** ({badge_spec}):\n"
                    + "\n".join([f"> {line}" for line in worker_result.split("\n")])
                )

        # 6. CONFIG_SET Tags
        for match in cls.PATTERNS["CONFIG_SET"].finditer(text):
            key = match.group(1).strip()
            raw_val = match.group(2).strip()
            if key and raw_val:
                val: Any = True if raw_val.lower() == "true" else (False if raw_val.lower() == "false" else raw_val)
                try:
                    val = int(raw_val)
                except ValueError:
                    try:
                        val = float(raw_val)
                    except ValueError:
                        pass
                config_manager.set(key, val)
                config_manager.save()
                badges.append(f"> ⚙️ **{name} updated runtime configuration:** `{key}` = `{val}`")

        # 7. CREATE_PERSONA Tags
        for match in cls.PATTERNS["CREATE_PERSONA"].finditer(text):
            h_name = match.group(1).strip().lower().replace("@", "")
            raw_yaml = match.group(2).strip()
            if h_name and raw_yaml:
                p_dir = getattr(profile_manager, "profiles_dir", "profiles")
                os.makedirs(p_dir, exist_ok=True)
                yaml_file = os.path.join(p_dir, f"{h_name}.yaml")
                try:
                    with open(yaml_file, "w", encoding="utf-8") as f:
                        f.write(raw_yaml)
                    profile_manager.reload_profiles()
                    new_p = profile_manager.get_profile(h_name)
                    p_disp = new_p.get("name", h_name) if new_p else h_name
                    badges.append(f"> 🧬 **{name} created new agent persona:** `@{h_name}` ({p_disp})")
                except Exception as e:
                    badges.append(f"> ⚠️ **Error creating persona `@{h_name}`:** {e}")

        # 8. DELETE_PERSONA Tags
        for match in cls.PATTERNS["DELETE_PERSONA"].finditer(text):
            h_name = match.group(1).strip().lower().replace("@", "")
            if h_name == "samantha":
                badges.append(f"> ⚠️ **Protected Persona:** `@samantha` cannot be deleted.")
                continue

            p_dir = getattr(profile_manager, "profiles_dir", "profiles")
            arch_dir = os.path.join(p_dir, "_archived", h_name)

            files_to_move = []
            for ext in (".yaml", "_soul.md", "_memory.md"):
                src = os.path.join(p_dir, f"{h_name}{ext}")
                if os.path.exists(src):
                    files_to_move.append((src, os.path.join(arch_dir, f"{h_name}{ext}")))

            if files_to_move:
                os.makedirs(arch_dir, exist_ok=True)
                for src, dst in files_to_move:
                    try:
                        shutil.move(src, dst)
                    except Exception:
                        pass
                profile_manager.reload_profiles()
                if config_manager.get("runtime.default_persona") == h_name:
                    config_manager.set("runtime.default_persona", "samantha")
                    config_manager.save()
        # 9. WRITE_CANVAS Tags (Slack Channel Canvas or Obsidian .canvas)
        for match in cls.PATTERNS["WRITE_CANVAS"].finditer(text):
            target, content = match.group(1).strip(), match.group(2).strip()
            if target and content:
                if target.startswith("#") or target.startswith("C0") or target.lower().startswith("slack:"):
                    badges.append(f"> 📋 **{name} published Slack Canvas to `{target.replace('slack:', '').strip()}`**")
                else:
                    fname = target if target.endswith(".canvas") or target.endswith(".md") else f"{target}.canvas"
                    VaultManager.write_note(profile, fname, content)
                    rel_path = f"{vault_folder}/{fname}" if vault_folder else fname
                    badges.append(f"> 🎨 **{name} created Visual Canvas in Vault:** `{rel_path}`")

        clean_text = text
        for p in cls.PATTERNS.values(): clean_text = p.sub("", clean_text).strip()
        return clean_text, badges
