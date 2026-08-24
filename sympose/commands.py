"""
Slash Command Interceptor & Natural Intent Parser for Sympose.
"""

import os
import shutil
import re
from typing import Any, Dict, Optional, Generator
from sympose.vault import VaultManager
from sympose.skills import skill_manager
from sympose.workers import WorkerEngine, WorkerTask
from sympose.mcp import mcp_registry


class CommandInterceptor:
    """Intercepts tactical slash commands and natural memory capture."""

    @staticmethod
    def intercept(engine: Any, handle: str, clean_input: str) -> Optional[Generator[str, None, None]]:
        """Checks if input matches a slash command or natural intent, returning a generator if so."""
        profile = engine.pm.get_profile(handle)
        if not profile:
            return None

        # 1. Reset / New Session
        if clean_input in ("/reset", "/new"):
            def _reset():
                engine.reset_history(handle)
                yield f"Reset conversation history for {profile.get('name', handle)}. Context refreshed."
            return _reset()

        # 2. Clear Screen & History
        if clean_input in ("/clear", "/cls"):
            def _clear():
                engine.reset_history(handle)
                yield "CLEARED_SESSION"
            return _clear()

        # 3. On-Demand Session Save
        if clean_input.startswith("/save"):
            def _save():
                parts = clean_input.split()
                def_t = engine.config.get("session.exit_behavior.default_target", "both")
                target = parts[1].lower() if len(parts) > 1 else def_t
                if target not in ("memory", "obsidian", "both"):
                    target = "both"
                yield f"Synthesizing and saving session to `{target}`..."
                res = engine.summarize_session(handle, target=target)
                if res.get("status") == "success":
                    saved_str = "\n".join([f"- {s}" for s in res.get("targets_saved", [])])
                    yield f"\n\n**Session Saved Successfully:**\n{saved_str}"
                else:
                    yield f"\n\n⚠️ {res.get('message', 'Failed to save session.')}"
            return _save()

        # 4. Master Configuration (/config)
        if clean_input.startswith("/config"):
            def _config():
                parts = clean_input.split(maxsplit=3)
                if len(parts) == 1:
                    cfg = engine.config
                    yield (
                        "**Sympose Active Configuration:**\n"
                        f"- `performance.request_timeout`: {cfg.get('performance.request_timeout')}s\n"
                        f"- `performance.max_context_turns`: {cfg.get('performance.max_context_turns')} turns\n"
                        f"- `performance.max_worker_tool_turns`: {cfg.get('performance.max_worker_tool_turns')} turns\n"
                        f"- `performance.stream`: {cfg.get('performance.stream')}\n"
                        f"- `session.exit_behavior.auto_save`: {cfg.get('session.exit_behavior.auto_save')}\n"
                        f"- `session.exit_behavior.default_target`: {cfg.get('session.exit_behavior.default_target')}\n"
                        f"- `session.exit_behavior.clear_terminal`: {cfg.get('session.exit_behavior.clear_terminal')}\n"
                        f"- `session.exit_behavior.summarization_model`: {cfg.get('session.exit_behavior.summarization_model')}\n"
                        f"- `vault.search_mode`: {cfg.get('vault.search_mode')}\n\n"
                        "Tip: Set values live with `/config set <key> <value>` (e.g. `/config set performance.max_context_turns 20`)."
                    )
                elif parts[1].lower() == "set" and len(parts) >= 4:
                    key, raw_val = parts[2], parts[3]
                    val: Any = True if raw_val.lower() == "true" else (False if raw_val.lower() == "false" else raw_val)
                    try:
                        val = int(raw_val)
                    except ValueError:
                        try:
                            val = float(raw_val)
                        except ValueError:
                            pass
                    engine.config.set(key, val)
                    if "max_context_turns" in key:
                        engine.max_turns = int(val)
                    yield f"Config `{key}` updated to `{val}` for active runtime."
                else:
                    yield "Usage:\n- `/config`: Show settings\n- `/config set <key> <value>`: Update setting"
            return _config()

        # 5. Explicit /remember
        if clean_input.startswith("/remember "):
            def _rem():
                fact = clean_input[10:].strip()
                if not fact:
                    yield "Usage: `/remember <fact to save>`"
                    return
                if engine.pm.append_memory(handle, fact):
                    yield f"Saved to {profile.get('name', handle)}'s memory:\n> {fact}"
                else:
                    yield f"Error: Failed to save memory to {profile.get('name', handle)}."
            return _rem()

        # 6. Model & Vault Handlers
        if clean_input.startswith("/model "):
            def _model():
                new_model = clean_input[7:].strip()
                engine.model_overrides[handle.lower()] = new_model
                yield f"Model for {profile.get('name', handle)} temporarily set to `{new_model}`."
            return _model()

        if clean_input.startswith("/vault "):
            def _vault():
                yield VaultManager.search(profile, clean_input[7:].strip())
            return _vault()

        if clean_input.startswith("/note "):
            def _note():
                parts = clean_input[6:].strip().split(maxsplit=1)
                yield VaultManager.write_note(profile, parts[0], parts[1]) if len(parts) >= 2 else "Usage: `/note <file.md> <content>`"
            return _note()

        if clean_input.startswith("/daily "):
            def _daily():
                yield VaultManager.write_daily_note(profile, clean_input[7:].strip()) if clean_input[7:].strip() else "Usage: `/daily <reflection>`"
            return _daily()

        if clean_input.startswith("/ask "):
            def _ask():
                parts = clean_input[5:].strip().split(maxsplit=1)
                if len(parts) < 2:
                    yield "Usage: `/ask <@persona> <task>`"
                    return
                target = parts[0].replace("@", "").lower()
                target_p = engine.pm.get_profile(target)
                if not target_p:
                    yield f"Specialist agent `@{target}` not found."
                    return
                yield f"[Delegating to {target_p.get('name', target)} ({target_p.get('title', 'Specialist')}):]\n\n"
                for chunk in engine.spawn_sub_agent(target, parts[1]):
                    yield chunk
            return _ask()

        # 7. Skills & MCP Inspection (/skills)
        if clean_input in ("/skills", "/tools"):
            def _skills():
                loaded_skills = skill_manager.list_skills()
                lines = ["**Installed Procedural Skill Playbooks (`skills/`):**"]
                if loaded_skills:
                    for s in loaded_skills:
                        lines.append(f"- **`{s['name']}`**: {s['title']} — *{s['description'] or 'No description'}*")
                else:
                    lines.append("- *No skill playbooks found in `skills/`.*")

                lines.append("\n**Configured MCP Tool Servers (`config.yaml`):**")
                if mcp_registry.servers:
                    for name, srv in mcp_registry.servers.items():
                        cmd_str = f"{srv['command']} {' '.join(srv['args'])}"
                        lines.append(f"- **`{name}`**: `{cmd_str}`")
                else:
                    lines.append("- *No MCP servers configured.*")

                yield "\n".join(lines)
            return _skills()

        # 8. Ephemeral Sub-Agent Worker Dispatch (/worker)
        if clean_input.startswith("/worker "):
            def _worker():
                parts = clean_input[8:].strip().split(maxsplit=1)
                if len(parts) < 2:
                    yield "Usage: `/worker <skill_or_mcp> <task prompt>`\nExample: `/worker git_workflow summarize uncommitted git diffs`"
                    return
                spec, task_prompt = parts[0], parts[1]
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
                yield f"🛠️ **Dispatching Ephemeral Sub-Agent Worker** (Skills: `{skills_to_load}`, MCP: `{mcp_to_load}`)...\n\n"
                for chunk in WorkerEngine.execute_worker_stream(task):
                    yield chunk
            return _worker()

        # 9. @mention in prompt
        mention_match = re.search(r"@(\w+)", clean_input)
        if mention_match:
            target_tag = mention_match.group(1).lower()
            if target_tag in engine.pm.profiles and target_tag != handle.lower():
                def _mention():
                    target_p = engine.pm.get_profile(target_tag)
                    yield f"[Delegating to {target_p.get('name', target_tag)} ({target_p.get('title', 'Specialist')}):]\n\n"
                    for chunk in engine.spawn_sub_agent(target_tag, clean_input):
                        yield chunk
                return _mention()

        # 10. Delete / Retire Persona
        if clean_input.startswith(("/delete", "/retire")):
            def _delete():
                parts = clean_input.split()
                if len(parts) < 2:
                    yield "Usage: `/delete @<handle>` (e.g. `/delete @curie`)"
                    return
                t_handle = parts[1].replace("@", "").lower()
                if t_handle == "samantha":
                    yield "⚠️ `@samantha` is the master orchestrator and cannot be deleted."
                    return
                p_dir = getattr(engine.pm, "profiles_dir", "profiles")
                arch_dir = os.path.join(p_dir, "_archived", t_handle)

                files_to_move = []
                for ext in (".yaml", "_soul.md", "_memory.md"):
                    src = os.path.join(p_dir, f"{t_handle}{ext}")
                    if os.path.exists(src):
                        files_to_move.append((src, os.path.join(arch_dir, f"{t_handle}{ext}")))

                if files_to_move:
                    os.makedirs(arch_dir, exist_ok=True)
                    for src, dst in files_to_move:
                        try:
                            shutil.move(src, dst)
                        except Exception:
                            pass
                    engine.pm.reload_profiles()
                    if engine.config.get("runtime.default_persona") == t_handle:
                        engine.config.set("runtime.default_persona", "samantha")
                        engine.config.save()
                    yield f"🗄️ **Retired agent persona @{t_handle}**. Files safely archived to `{arch_dir}/`."
                else:
                    engine.pm.reload_profiles()
                    yield f"⚠️ Persona `@{t_handle}` not found in `{p_dir}/`."
            return _delete()

        # 11. Help Menu
        if clean_input == "/help":
            def _help():
                yield (
                    "**Available Slash Commands:**\n"
                    "- `/skills` or `/tools`: Inspect indexed skill playbooks and MCP tool servers\n"
                    "- `/worker <skill|mcp> <task>`: Dispatch an isolated sub-agent worker with tools/skills\n"
                    "- `/save [memory|obsidian|both]`: Summarize and save session takeaways\n"
                    "- `/config`: View active runtime, performance & session settings\n"
                    "- `/config set <key> <val>`: Tune knobs live (e.g. `/config set performance.max_context_turns 20`)\n"
                    "- `/delete @<handle>`: Retire/archive an agent persona safely\n"
                    "- `/clear`: Clear terminal display and reset conversation context\n"
                    "- `/ask <@persona> <task>`: Delegate an isolated sub-task to a peer\n"
                    "- `/note <file.md> <content>`: Create or append to a sandboxed vault note\n"
                    "- `/daily <reflection>`: Append to Daily Notes/YYYY-MM-DD.md\n"
                    "- `/remember <fact>`: Save fact into persona's persistent `_memory.md`\n"
                    "- `/reset` or `/new`: Clear active conversation context\n"
                    "- `/model <name>`: Temporarily switch backend model\n"
                    "- `/vault <query>`: Query persona's sandboxed notes\n"
                    "- `/help`: Show this command list\n"
                    "- `quit` or `exit`: End session (triggers save options)"
                )
            return _help()

        return None
