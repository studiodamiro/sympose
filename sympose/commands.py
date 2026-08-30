"""
Slash Command Interceptor & Natural Intent Parser for Sympose.
"""

import os
import shutil
import re
import logging
from typing import Any, Dict, Optional, Generator
from sympose.vault import VaultManager
from sympose.skills import skill_manager
from sympose.workers import WorkerEngine, WorkerTask
from sympose.mcp import mcp_registry
from sympose.models import ModelCatalog
from sympose.sessions import SessionManager
from sympose.ui import TerminalUI
from sympose.config import DEFAULT_CHAT_MODEL

log = logging.getLogger(__name__)


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

        # 0. Setup & Onboarding Wizard
        if clean_input in ("/setup", "/onboard", "/wizard"):
            def _setup():
                from sympose.bootstrap import resolve_workspace_dir, run_first_run_onboarding
                workspace_dir = resolve_workspace_dir()
                run_first_run_onboarding(workspace_dir, force=True)
                yield "✨ Setup configuration updated."
            return _setup()

        # 0b. Conversation History & Session Resumption (/history, /sessions)
        if clean_input.startswith(("/history", "/sessions")):
            def _history():
                parts = clean_input.split()
                subcmd = parts[1].lower() if len(parts) > 1 else "list"
                console = TerminalUI.get_console()

                if subcmd in ("new", "create"):
                    engine.new_session(handle)
                    yield f"✨ Started fresh conversation session for {profile.get('name', handle)}."
                    return

                if subcmd in ("delete", "remove", "rm") and len(parts) > 2:
                    target_id = parts[2]
                    all_s = SessionManager.list_sessions(limit=50)
                    match = next((s["session_id"] for s in all_s if s["session_id"].startswith(target_id) or target_id in s["session_id"]), target_id)
                    if SessionManager.delete_session(match):
                        yield f"🗑️ Deleted session `{match}`."
                    else:
                        yield f"⚠️ Could not delete session `{target_id}` (not found)."
                    return

                if subcmd in ("view", "show") and len(parts) > 2:
                    target_id = parts[2]
                    all_s = SessionManager.list_sessions(limit=50)
                    match = next((s["session_id"] for s in all_s if s["session_id"].startswith(target_id) or target_id in s["session_id"]), target_id)
                    session = SessionManager.load_session(match)
                    if not session:
                        yield f"⚠️ Session `{target_id}` not found."
                        return
                    show_all = "--all" in parts
                    turns = session.get("turns", [])
                    disp_turns = turns if show_all else turns[-6:]
                    TerminalUI.render_session_resumed(console, session.get("title", ""), session.get("handle", handle), disp_turns)
                    yield ""
                    return

                if subcmd in ("resume", "load") and len(parts) > 2:
                    target_id = parts[2]
                    all_s = SessionManager.list_sessions(limit=50)
                    match = next((s["session_id"] for s in all_s if s["session_id"].startswith(target_id) or target_id in s["session_id"]), target_id)
                    session = engine.resume_session(handle, match)
                    if not session:
                        yield f"⚠️ Session `{target_id}` not found."
                        return
                    turns = session.get("turns", [])
                    k_turns = int(engine.config.get("performance.resume_context_turns", 6))
                    disp_turns = turns[-k_turns:] if k_turns > 0 else turns
                    TerminalUI.render_session_resumed(console, session.get("title", ""), session.get("handle", handle), disp_turns)
                    yield ""
                    return

                # Interactive listing: /history, /history list, /history all
                is_all = (subcmd in ("all", "--all") or (len(parts) > 2 and parts[2] in ("all", "--all")))
                target_handle = None if is_all else handle
                active_sid = engine.active_sessions.get(handle.lower())
                sessions = SessionManager.list_sessions(handle=target_handle, limit=15, active_session_id=active_sid)

                if not sessions:
                    yield f"No past conversations found{' for @' + handle if not is_all else ''}."
                    return

                chosen_id = TerminalUI.select_session(
                    console,
                    sessions,
                    active_session_id=engine.active_sessions.get(handle.lower()),
                    handle=handle if not is_all else None,
                    show_handle=is_all
                )

                if not chosen_id:
                    yield "History selection cancelled."
                    return

                session = engine.resume_session(handle, chosen_id)
                if session:
                    turns = session.get("turns", [])
                    k_turns = int(engine.config.get("performance.resume_context_turns", 6))
                    disp_turns = turns[-k_turns:] if k_turns > 0 else turns
                    TerminalUI.render_session_resumed(console, session.get("title", ""), session.get("handle", handle), disp_turns)
                    yield ""
                else:
                    yield f"⚠️ Could not load session `{chosen_id}`."
            return _history()

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
                    except Exception as e: log.debug("[reset memory] failed to read template %s: %s", template_file, e)
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
                        "# ⚙️  ACTIVE RUNTIME CONFIGURATION\n\n"
                        "### ⚡  PERFORMANCE & STREAMING\n"
                        f"- `performance.request_timeout`: `{cfg.get('performance.request_timeout')}s`\n"
                        f"- `performance.local_request_timeout`: `{cfg.get('performance.local_request_timeout', 120.0)}s`\n"
                        f"- `performance.max_context_turns`: `{cfg.get('performance.max_context_turns')} turns`\n"
                        f"- `performance.resume_context_turns`: `{cfg.get('performance.resume_context_turns', 6)} turns`\n"
                        f"- `performance.max_worker_tool_turns`: `{cfg.get('performance.max_worker_tool_turns')} turns`\n"
                        f"- `performance.stream`: `{cfg.get('performance.stream')}`\n\n"
                        "### 💾  SESSION & MEMORY ARCHIVAL\n"
                        f"- `session.exit_behavior.auto_save`: `{cfg.get('session.exit_behavior.auto_save')}`\n"
                        f"- `session.exit_behavior.default_target`: `{cfg.get('session.exit_behavior.default_target')}`\n"
                        f"- `session.exit_behavior.clear_terminal`: `{cfg.get('session.exit_behavior.clear_terminal')}`\n"
                        f"- `session.exit_behavior.summarization_model`: `{cfg.get('session.exit_behavior.summarization_model') or DEFAULT_CHAT_MODEL}`\n"
                        f"- `memory.compaction_threshold`: `{cfg.get('memory.compaction_threshold', 25)} lines`\n"
                        f"- `memory.auto_compact`: `{cfg.get('memory.auto_compact', True)}`\n"
                        f"- `vault.search_mode`: `{cfg.get('vault.search_mode')}`\n\n"
                        "### 💡  LIVE TUNING\n"
                        "- Tune knobs live with `/config set <key> <value>` (e.g. `/config set performance.max_context_turns 20`)."
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
                    yield f"✅ Config `{key}` updated to `{val}` (persisted to disk)."
                else:
                    yield "Usage:\n- `/config`: Show active settings\n- `/config set <key> <value>`: Update setting live"
            return _config()

        # 4b. Render Mode Switcher (/render)
        if clean_input == "/render" or clean_input.startswith("/render "):
            def _render():
                parts = clean_input.split()
                sub = parts[1].lower() if len(parts) > 1 else ""
                current_mode = str(engine.config.get("performance.render_mode", "hybrid")).lower()
                console = TerminalUI.get_console()

                if not sub:
                    chosen = TerminalUI.select_render_mode(console, current_mode)
                    if chosen:
                        engine.config.set("performance.render_mode", chosen)
                        engine.config.save()
                        yield f"✅ Terminal render mode updated to **`{chosen}`** (persisted to config.yaml)."
                    else:
                        yield ""
                    return

                mode_map = {
                    "1": "hybrid", "hybrid": "hybrid", "smart": "hybrid",
                    "2": "buffered", "buffered": "buffered", "full": "buffered", "markdown": "buffered",
                    "3": "raw", "raw": "raw", "plain": "raw"
                }
                if sub in mode_map:
                    target_mode = mode_map[sub]
                    engine.config.set("performance.render_mode", target_mode)
                    engine.config.save()
                    yield f"✅ Terminal render mode updated to **`{target_mode}`** (persisted to config.yaml)."
                else:
                    yield "⚠️ Invalid render mode. Available options: `hybrid`, `buffered`, `raw`."
            return _render()

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
                default_model = profile.get("model") or DEFAULT_CHAT_MODEL
                current_model = active_override or default_model

                if not sub or sub_lower in ("list", "help", "status", "ls"):
                    or_key = "✅ Configured" if os.getenv("OPENROUTER_API_KEY") else "❌ Missing (add OPENROUTER_API_KEY to .env)"
                    gem_key = "✅ Configured" if os.getenv("GEMINI_API_KEY") else "❌ Missing (add GEMINI_API_KEY to .env)"
                    ant_key = "✅ Configured" if os.getenv("ANTHROPIC_API_KEY") else "❌ Missing (add ANTHROPIC_API_KEY to .env)"
                    oai_key = "✅ Configured" if os.getenv("OPENAI_API_KEY") else "❌ Missing (add OPENAI_API_KEY to .env)"

                    state_tag = f"`{current_model}` (Live Session Override)" if active_override else f"`{current_model}` (Profile Default)"

                    lines = [
                        "# 🤖  MODEL & PROVIDER CONFIGURATION\n",
                        "### 🎯  ACTIVE MODEL",
                        f"- **Current Model:** {state_tag}",
                        f"- **Active Persona:** {profile.get('name', handle)} (`@{handle}`)\n",
                        "### 🔑  CONFIGURED PROVIDERS (.ENV)",
                        f"- **OpenRouter:** {or_key}",
                        f"- **Google Gemini:** {gem_key}",
                        f"- **Anthropic Claude:** {ant_key}",
                        f"- **OpenAI:** {oai_key}\n",
                        "### 🌟  RECOMMENDED MODELS TO TEST",
                        "- **OpenRouter (Multi-Provider):**",
                        "  - `openrouter/anthropic/claude-3.5-sonnet` — Surgical coding & architecture",
                        "  - `openrouter/deepseek/deepseek-r1` — Deep reasoning & algorithmic thought",
                        "  - `openrouter/google/gemini-2.5-flash` — Fast, multimodal agentic worker",
                        "  - `openrouter/meta-llama/llama-3.3-70b-instruct` — High-density open weights",
                        "- **Direct Cloud API Keys:**",
                        f"  - `{DEFAULT_CHAT_MODEL}` — Sub-second low latency",
                        "  - `anthropic/claude-3-5-sonnet-20241022` — Direct Anthropic API",
                        "- **Local Ollama:**",
                        "  - `ollama/qwen2.5:7b` — Sovereign local execution\n",
                        "### 💡  COMMANDS & NAVIGATION",
                        "- Search catalog: `/model find <keyword>` (e.g. `/model find sonnet`, `/model find deepseek`)",
                        "- Switch model: `/model <model_id>` (e.g. `/model openrouter/anthropic/claude-3.5-sonnet`)",
                        "- Refresh catalog cache: `/model refresh`",
                        "- Revert to default model: `/model reset`",
                        "- Setup wizard: `/setup`",
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

        # 6. Sandboxed Vault & Markdown Explorer (/vault, /read, /view, /open, /backlinks)
        if clean_input.startswith(("/vault", "/backlinks", "/read", "/view", "/open")):
            def _vault_ops():
                raw = clean_input.strip()
                console = TerminalUI.get_console()

                # 6a. Backlinks lookup
                if raw.startswith("/vault backlinks") or raw.startswith("/backlinks"):
                    target = raw[16:].strip() if raw.startswith("/vault backlinks") else raw[10:].strip()
                    if not target:
                        yield "Usage: `/vault backlinks <note_name>` or `/backlinks <note_name>`"
                        return
                    yield VaultManager.get_backlinks_digest(profile, target)
                    return

                # 6b. Open in Obsidian / system editor (/open <#|note> or /vault open <#|note>)
                if raw.startswith("/vault open ") or raw.startswith("/open "):
                    target = raw[12:].strip() if raw.startswith("/vault open ") else raw[6:].strip()
                    if not target:
                        yield "Usage: `/open <#|note_name>` or `/vault open <#|note_name>`"
                        return
                    ok, msg = VaultManager.open_in_obsidian(profile, target)
                    yield f"✨ {msg}" if ok else f"⚠️ {msg}"
                    return

                # 6c. Read / View note in boxed terminal panel (/read <#|note> or /view <#|note> or /vault read <#|note>)
                if raw.startswith(("/read ", "/view ", "/vault read ")):
                    if raw.startswith("/vault read "):
                        target = raw[12:].strip()
                    elif raw.startswith("/read "):
                        target = raw[6:].strip()
                    else:
                        target = raw[6:].strip()

                    if not target:
                        yield "Usage: `/read <#|note_name>` or `/view <#|note_name>`"
                        return

                    rel_path, abs_path = VaultManager.resolve_note_target(profile, target)
                    if not rel_path:
                        yield f"⚠️ Note `{target}` not found in allowed vault folders."
                        return

                    content = VaultManager.read_note(profile, rel_path)
                    cached = VaultManager.get_last_search(profile)
                    if console:
                        if cached and target.isdigit() and 1 <= int(target) <= len(cached):
                            TerminalUI.interactive_vault_browser(console, profile, "Search", cached, initial_index=int(target))
                        else:
                            TerminalUI.render_vault_note_panel(console, rel_path, content, abs_path=abs_path)
                        yield ""
                    else:
                        yield f"### 📄 Note: `{rel_path}`\n\n{content}"
                    return

                # 6d. Re-display previous search results (/vault, /vault back, /vault list, /vaults)
                if raw in ("/vault", "/vaults", "/vault back", "/vault list", "/vault prev"):
                    cached = VaultManager.get_last_search(profile)
                    if not cached:
                        yield "No previous search results found in session. Run `/vault <query>` to search."
                        return
                    if console:
                        TerminalUI.interactive_vault_browser(console, profile, "Previous Search", cached)
                        yield ""
                    else:
                        yield VaultManager.format_search_digest("Previous Search", cached)
                    return

                # 6e. Direct search query or number selection (/vault <query> or /vault <#>)
                query = raw[7:].strip() if raw.startswith("/vault ") else raw[6:].strip()
                if not query:
                    cached = VaultManager.get_last_search(profile)
                    if cached and console:
                        TerminalUI.interactive_vault_browser(console, profile, "Previous Search", cached)
                        yield ""
                    else:
                        yield "Usage: `/vault <query>` or `/vault backlinks <note>` or `/vault back`"
                    return

                cached = VaultManager.get_last_search(profile)
                if query.isdigit() and cached:
                    idx = int(query)
                    if 1 <= idx <= len(cached):
                        if console:
                            TerminalUI.interactive_vault_browser(console, profile, "Search", cached, initial_index=idx)
                            yield ""
                        else:
                            item = cached[idx - 1]
                            content = VaultManager.read_note(profile, item["rel_path"])
                            yield f"### 📄 Note: `{item['rel_path']}`\n\n{content}"
                        return

                results = VaultManager.search_structured(profile, query)
                if console:
                    TerminalUI.interactive_vault_browser(console, profile, query, results)
                    yield ""
                else:
                    yield VaultManager.format_search_digest(query, results)

            return _vault_ops()

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

        # 7. Skills & MCP Inspection & Management (/skill, /skills, /tools)
        if clean_input.startswith(("/skill", "/skills", "/tools")):
            def _skills():
                parts = clean_input.split()
                sub = parts[1].lower() if len(parts) > 1 else "list"

                # 7a. Show / View / Info on a specific skill
                if sub in ("show", "view", "info"):
                    if len(parts) < 3:
                        yield "Usage: `/skill show <skill_name>` (e.g. `/skill show git_workflow`)"
                        return
                    s_name = parts[2].lower()
                    skill = skill_manager.get_skill(s_name)
                    if not skill:
                        yield f"⚠️ Skill `{s_name}` not found. Run `/skill list` to see all available skills."
                        return
                    tags_str = f"- **Tags:** `{', '.join(skill.tags)}`\n" if skill.tags else ""
                    mcp_str = f"- **MCP Dependencies:** `{', '.join(skill.mcp_servers)}`\n" if skill.mcp_servers else ""
                    models_str = f"- **Recommended Models:** `{', '.join(skill.recommended_models)}`\n" if skill.recommended_models else ""
                    yield (
                        f"# 📦  SKILL: {skill.title.upper()} (`{skill.name}`)\n\n"
                        f"- **Description:** *{skill.description or 'No description'}*\n"
                        f"- **File:** `{skill.filepath}`\n"
                        f"{tags_str}{mcp_str}{models_str}\n"
                        f"---\n\n"
                        f"### 📋 Playbook Directives:\n\n"
                        f"{skill.content}\n\n"
                        f"---\n"
                        f"*To mount to active persona:* `/skill add {skill.name}`\n"
                        f"*To mount to specific agent:* `/skill add {skill.name} @<handle>`"
                    )
                    return

                # 7b. Add / Mount / Install skill to persona
                if sub in ("add", "mount", "install"):
                    if len(parts) < 3:
                        yield "Usage: `/skill add <skill_name> [@handle]`\nExample: `/skill add git_workflow @rosalind`"
                        return
                    s_name = parts[2].lower()
                    t_handle = parts[3].replace("@", "").lower() if len(parts) > 3 else handle.lower()
                    skill = skill_manager.get_skill(s_name)
                    if not skill:
                        yield f"⚠️ Warning: Skill `{s_name}` is not indexed in `skills/` or builtin skills. (Run `/skill list` to view available skills)."
                    ok, msg = engine.pm.update_persona_skills(t_handle, s_name, action="add")
                    yield f"✅ {msg}" if ok else f"⚠️ {msg}"
                    return

                # 7c. Remove / Unmount / Uninstall skill from persona
                if sub in ("remove", "unmount", "uninstall", "rm"):
                    if len(parts) < 3:
                        yield "Usage: `/skill remove <skill_name> [@handle]`\nExample: `/skill remove git_workflow @rosalind`"
                        return
                    s_name = parts[2].lower()
                    t_handle = parts[3].replace("@", "").lower() if len(parts) > 3 else handle.lower()
                    ok, msg = engine.pm.update_persona_skills(t_handle, s_name, action="remove")
                    yield f"✅ {msg}" if ok else f"⚠️ {msg}"
                    return

                # 7d. Shortcut: Direct skill name lookup (e.g. `/skill git_workflow`)
                if sub not in ("list", "ls") and (direct_skill := skill_manager.get_skill(sub)):
                    tags_str = f"- **Tags:** `{', '.join(direct_skill.tags)}`\n" if direct_skill.tags else ""
                    yield (
                        f"# 📦  SKILL: {direct_skill.title.upper()} (`{direct_skill.name}`)\n\n"
                        f"- **Description:** *{direct_skill.description or 'No description'}*\n"
                        f"- **File:** `{direct_skill.filepath}`\n"
                        f"{tags_str}\n"
                        f"---\n\n"
                        f"### 📋 Playbook Directives:\n\n"
                        f"{direct_skill.content}\n\n"
                        f"---\n"
                        f"*To mount to active persona:* `/skill add {direct_skill.name}`\n"
                        f"*To mount to specific agent:* `/skill add {direct_skill.name} @<handle>`"
                    )
                    return

                # 7e. Default: List all skills and active personas
                loaded_skills = skill_manager.list_skills()
                engine.pm.reload_profiles()
                equipped_map: Dict[str, list] = {}
                for p_h, p_data in engine.pm.profiles.items():
                    for sk in (p_data.get("skills") or []):
                        equipped_map.setdefault(sk.lower(), []).append(f"@{p_h}")

                curr_skills = profile.get("skills") or []
                curr_sk_str = ", ".join(f"`{s}`" for s in curr_skills) if curr_skills else "*None*"

                lines = [
                    "# 🛠️  INSTALLED SKILLS & MCP TOOL SERVERS\n",
                    f"### 👤  ACTIVE PERSONA: {profile.get('name', handle)} (`@{handle}`)",
                    f"- **Equipped Skills:** {curr_sk_str}\n",
                    "### 📦  AVAILABLE PROCEDURAL SKILL PLAYBOOKS (`skills/`)"
                ]
                if loaded_skills:
                    for s in loaded_skills:
                        eq_list = equipped_map.get(s["name"].lower(), [])
                        eq_str = f" *(Equipped: {', '.join(eq_list)})*" if eq_list else ""
                        lines.append(f"- **`{s['name']}`**: {s['title']} — *{s['description'] or 'No description'}*{eq_str}")
                else:
                    lines.append("- *No skill playbooks found in `skills/`.*")

                lines.append("\n### 🔌  CONFIGURED MCP TOOL SERVERS (`config.yaml`)")
                if mcp_registry.servers:
                    for name, srv in mcp_registry.servers.items():
                        cmd_str = f"{srv['command']} {' '.join(srv['args'])}"
                        lines.append(f"- **`{name}`**: `{cmd_str}`")
                else:
                    lines.append("- *No MCP servers configured.*")

                lines.append("\n### 💡  SKILL MANAGEMENT COMMANDS")
                lines.append("- Mount skill to active agent: `/skill add <skill_name>`")
                lines.append("- Mount skill to specific agent: `/skill add <skill_name> @<handle>`")
                lines.append("- Unmount skill from agent: `/skill remove <skill_name> [@handle]`")
                lines.append("- Inspect playbook directives: `/skill show <skill_name>`")
                lines.append("- Run one-off task with skill: `/worker <skill_name> <task prompt>`")

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
                    "# 🏛️  SYMPOSE HUB COMMANDS\n\n"
                    "### 👥  SESSION & PERSONA CONTROL\n"
                    "- `/history [list|all|new|resume <id>]` — List and resume past conversations\n"
                    "- `/switch [@handle]` — Switch active specialist persona\n"
                    "- `/setup` or `/onboard` — Launch interactive provider & vault setup wizard\n"
                    "- `/model [id | reset]` — Inspect provider status or switch backend model\n"
                    "- `/clear` — Clear terminal display & reset active context\n"
                    "- `/reset` or `/new` — Wipe current conversation history\n"
                    "- `quit` or `exit` — End session (triggers save prompt)\n\n"
                    "### 📚  KNOWLEDGE & OBSIDIAN VAULT\n"
                    "- `/vault <query>` — Search notes within authorized sandbox\n"
                    "- `/vault backlinks <note>` — Inspect incoming references for a note\n"
                    "- `/note <file.md> <content>` — Create or append to a sandboxed note\n"
                    "- `/daily <reflection>` — Append reflection to today's Daily Note\n"
                    "- `/remember <fact>` — Save fact into persona's persistent memory\n"
                    "- `/compact [shared|@handle]` — Consolidate duplicate memory bullets\n"
                    "- `/save [memory|obsidian|both]` — Manually trigger session summary\n\n"
                    "### 🛠️  SUB-AGENTS & TOOLS\n"
                    "- `/skills` or `/skill [list]` — Inspect indexed skill playbooks and active mounts\n"
                    "- `/skill add <name> [@handle]` — Mount skill to active agent (or @handle)\n"
                    "- `/skill remove <name> [@handle]` — Unmount skill from agent\n"
                    "- `/skill show <name>` — Inspect playbook directives & markdown source\n"
                    "- `/worker <skill|mcp> <task>` — Dispatch ephemeral sub-agent worker\n"
                    "- `/ask <@handle> <task>` — Delegate isolated sub-task to a peer\n\n"
                    "### ⚙️  RUNTIME SETTINGS\n"
                    "- `/render [hybrid|buffered|raw]` — Switch terminal render mode (interactive menu or direct)\n"
                    "- `/config` — View active runtime settings & performance knobs\n"
                    "- `/config set <key> <val>` — Live-tune knobs (e.g. `/config set performance.max_context_turns 20`)\n"
                    "- `/delete @<handle>` — Safely archive & retire an agent persona\n"
                    "- `/help` — Show this command reference"
                )
            return _help()

        return None
