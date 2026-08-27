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
from sympose.models import ModelCatalog


class CommandInterceptor:
    """Intercepts tactical slash commands and natural memory capture."""

    @staticmethod
    def intercept(engine: Any, handle: str, clean_input: str) -> Optional[Generator[str, None, None]]:
        """Checks if input matches a slash/exclamation command or natural intent, returning a generator if so."""
        profile = engine.pm.get_profile(handle)
        if not profile:
            return None

        if clean_input.startswith("!"):
            clean_input = "/" + clean_input[1:]

        # 1. Reset / New Session / Delete Conversation
        if clean_input in ("/reset", "/new") or re.search(r"^(?:please\s+)?(?:delete|clear|reset|wipe|start\s+a\s+new)\s+(?:our\s+|the\s+|this\s+)?(?:chat|conversation|history|session)$", clean_input, re.I):
            def _reset():
                engine.reset_history(handle)
                yield f"🧹 Conversation history deleted for {profile.get('name', handle)}. Context refreshed."
            return _reset()

        # 2. Clear Screen & Terminal Session
        if clean_input in ("/clear", "/cls"):
            def _clear():
                engine.reset_history(handle)
                yield "CLEARED_SESSION"
            return _clear()

        # 2b. Reset / Wipe Working Memory
        if clean_input in ("/reset memory", "/clear memory") or re.search(r"^(?:please\s+)?(?:delete|clear|wipe|reset)\s+(?:your\s+|all\s+)?memory$", clean_input, re.I):
            def _reset_mem():
                mem_file = profile.get("memory_file", f"profiles/{handle}_memory.md")
                p_name = profile.get("name", handle)
                template_file = f"{mem_file}.example"
                initial_content = f"# {p_name}: Persistent Working Memory\n\n"
                if os.path.exists(template_file):
                    try:
                        with open(template_file, "r", encoding="utf-8") as tf: initial_content = tf.read()
                    except Exception: pass
                with open(mem_file, "w", encoding="utf-8") as f: f.write(initial_content)
                engine.reset_history(handle)
                yield f"🧠 Persistent working memory and active conversation deleted for {p_name}. Reset to clean template."
            return _reset_mem()

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
                        f"- `memory.compaction_threshold`: {cfg.get('memory.compaction_threshold', 25)} lines\n"
                        f"- `memory.auto_compact`: {cfg.get('memory.auto_compact', True)}\n"
                        f"- `vault.search_mode`: {cfg.get('vault.search_mode')}\n\n"
                        "Tip: Set values live with `/config set <key> <value>` (e.g. `/config set memory.compaction_threshold 25`)."
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
                    engine.config.save()
                    if "max_context_turns" in key:
                        engine.max_turns = int(val)
                    yield f"Config `{key}` updated to `{val}` (persisted to disk)."
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

        # 5b. Memory Compactor (/compact)
        if clean_input == "/compact" or clean_input.startswith("/compact "):
            def _compact():
                parts = clean_input.split()
                target_arg = parts[1].lower().replace("@", "") if len(parts) > 1 else handle.lower()
                from sympose.compactor import MemoryCompactor

                if target_arg in ("shared", "all", "team"):
                    shared_file = os.path.join(getattr(engine.pm, "profiles_dir", "profiles"), "_shared_memory.md")
                    before_count = MemoryCompactor.count_bullet_lines(shared_file)
                    yield f"🧹 **Compacting Shared Team Working Memory** (`{shared_file}`, {before_count} entries)..."
                    ok = MemoryCompactor.compact_file(shared_file, is_shared=True)
                    if ok:
                        after_count = MemoryCompactor.count_bullet_lines(shared_file)
                        yield f"\n\n✅ **Compaction Complete:** Shared memory consolidated from {before_count} to {after_count} high-density bullets."
                    else:
                        yield f"\n\n⚠️ Compaction failed or memory file is empty."
                else:
                    t_prof = engine.pm.get_profile(target_arg)
                    if not t_prof:
                        yield f"⚠️ Persona `@{target_arg}` not found. Usage: `/compact` or `/compact shared`."
                        return
                    mem_file = t_prof.get("memory_file", f"profiles/{target_arg}_memory.md")
                    before_count = MemoryCompactor.count_bullet_lines(mem_file)
                    p_name = t_prof.get("name", target_arg)
                    yield f"🧹 **Compacting {p_name}'s Working Memory** (`{mem_file}`, {before_count} entries)..."
                    ok = MemoryCompactor.compact_file(mem_file, is_shared=False)
                    if ok:
                        after_count = MemoryCompactor.count_bullet_lines(mem_file)
                        yield f"\n\n✅ **Compaction Complete:** {p_name}'s memory consolidated from {before_count} to {after_count} high-density bullets."
                    else:
                        yield f"\n\n⚠️ Compaction failed or memory file is empty."
            return _compact()

        # 6. Model & Vault Handlers
        if clean_input == "/model" or clean_input.startswith("/model "):
            def _model():
                parts = clean_input.split(maxsplit=1)
                sub = parts[1].strip() if len(parts) > 1 else ""
                sub_lower = sub.lower()
                active_override = engine.model_overrides.get(handle.lower())
                default_model = profile.get("model", "gemini/gemini-3.5-flash-lite")
                current_model = active_override or default_model

                if not sub or sub_lower in ("list", "help", "status", "ls"):
                    or_key = "✅ Configured" if os.getenv("OPENROUTER_API_KEY") else "❌ Missing (add OPENROUTER_API_KEY to .env)"
                    gem_key = "✅ Configured" if os.getenv("GEMINI_API_KEY") else "❌ Missing (add GEMINI_API_KEY to .env)"
                    ant_key = "✅ Configured" if os.getenv("ANTHROPIC_API_KEY") else "❌ Missing (add ANTHROPIC_API_KEY to .env)"
                    oai_key = "✅ Configured" if os.getenv("OPENAI_API_KEY") else "❌ Missing (add OPENAI_API_KEY to .env)"

                    state_tag = f"`{current_model}` (Live Session Override)" if active_override else f"`{current_model}` (Profile Default)"

                    lines = [
                        f"**Active Model for {profile.get('name', handle)}:** {state_tag}",
                        "\n**Configured Providers (.env):**",
                        f"- OpenRouter: {or_key}",
                        f"- Google Gemini: {gem_key}",
                        f"- Anthropic Claude: {ant_key}",
                        f"- OpenAI: {oai_key}",
                        "\n**Recommended Models to Test:**",
                        "- **OpenRouter:**",
                        "  - `openrouter/anthropic/claude-sonnet-4.5` (Surgical coding & architecture)",
                        "  - `openrouter/deepseek/deepseek-v4-pro` (Deep reasoning & fullstack)",
                        "  - `openrouter/google/gemini-3.7-flash` (Fast, multimodal agentic worker)",
                        "  - `openrouter/qwen/qwen3.8-27b` (High-density coding & tool calling)",
                        "- **Direct Cloud (Requires Direct Key):**",
                        "  - `gemini/gemini-3.5-flash-lite` (Sub-second low latency)",
                        "  - `anthropic/claude-3-5-sonnet-20241022` (Direct Anthropic key)",
                        "- **Local Ollama:**",
                        "  - `ollama/qwen2.5:7b`",
                        "\n**Usage:**",
                        "- Search catalog: `/model find <keyword>` (e.g. `/model find sonnet`, `/model find deepseek`)",
                        "- Switch model: `/model <model_id>` (e.g. `/model openrouter/anthropic/claude-sonnet-4.5`)",
                        "- Refresh cache: `/model refresh`",
                        "- Revert to default: `/model reset`",
                    ]
                    yield "\n".join(lines)
                elif sub_lower.startswith(("find ", "search ")):
                    query = sub.split(maxsplit=1)[1].strip() if len(sub.split()) > 1 else ""
                    if not query:
                        yield "Usage: `/model find <keyword>` (e.g. `/model find sonnet`, `/model find deepseek`)"
                        return
                    matches = ModelCatalog.search_models(query, limit=10)
                    if matches:
                        res = [f"**OpenRouter Models Matching '{query}':**"]
                        for m in matches:
                            ctx_str = f"({m.get('context_length', 0) // 1000}k ctx)" if m.get("context_length") else ""
                            res.append(f"- **`openrouter/{m['id']}`** {ctx_str} — *{m.get('name', '')}*")
                        res.append(f"\n*To switch:* `/model openrouter/{matches[0]['id']}`")
                        yield "\n".join(res)
                    else:
                        yield f"No models found matching `{query}` in OpenRouter catalog. Run `/model refresh` to update."
                elif sub_lower == "refresh":
                    fresh = ModelCatalog.get_cached_models(force_refresh=True)
                    yield f"🔄 **Refreshed OpenRouter Catalog:** {len(fresh)} models indexed in local cache."
                elif sub_lower == "reset":
                    if handle.lower() in engine.model_overrides:
                        del engine.model_overrides[handle.lower()]
                    yield f"Reset model for {profile.get('name', handle)} back to profile default: `{default_model}`."
                else:
                    new_model = sub
                    engine.model_overrides[handle.lower()] = new_model
                    yield f"Model for {profile.get('name', handle)} temporarily set to `{new_model}`.\n*(Run `/model reset` to restore default)*"
            return _model()

        if clean_input.startswith("/vault ") or clean_input.startswith("/backlinks"):
            def _vault():
                raw = clean_input.strip()
                if raw.startswith("/vault backlinks") or raw.startswith("/backlinks"):
                    target = raw[16:].strip() if raw.startswith("/vault backlinks") else raw[10:].strip()
                    if not target:
                        yield "Usage: `/vault backlinks <note_name>` or `/backlinks <note_name>`"
                        return
                    yield VaultManager.get_backlinks_digest(profile, target)
                else:
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

        # 9. Explicit @mention delegation (must start with @<handle>)
        mention_match = re.match(r"^\s*@(\w+)(?:\s*[:,]?\s*(.*))?$", clean_input, re.DOTALL)
        if mention_match:
            target_tag = mention_match.group(1).lower()
            delegated_prompt = (mention_match.group(2) or "").strip() or clean_input
            if target_tag in engine.pm.profiles and target_tag != handle.lower():
                def _mention():
                    target_p = engine.pm.get_profile(target_tag)
                    yield f"[Delegating to {target_p.get('name', target_tag)} ({target_p.get('title', 'Specialist')}):]\n\n"
                    for chunk in engine.spawn_sub_agent(target_tag, delegated_prompt):
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
                    "- `/compact [shared|@persona]`: Consolidate duplicates, resolve conflicts, and prune memory\n"
                    "- `/reset` or `/new`: Clear active conversation context\n"
                    "- `/model [name|reset]`: View active model, provider health, or switch/reset backend model\n"
                    "- `/vault <query>`: Query persona's sandboxed notes\n"
                    "- `/vault backlinks <note>`: Query incoming backlinks/references for a note\n"
                    "- `/help`: Show this command list\n"
                    "- `quit` or `exit`: End session (triggers save options)"
                )
            return _help()

        return None
