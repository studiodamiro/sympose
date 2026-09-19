"""
Slash Command Interceptor & Natural Intent Parser for Sympose.

`intercept` used to be one ~1100-line function with every command handler
nested inside it as a closure over `engine`/`handle`/`clean_input`/
`profile`. mccabe's cyclomatic-complexity check counts a nested function's
own branching as part of its enclosing function's total, which is why
that one function alone measured complexity 151 — restructured here into
a data-driven dispatch table: each command is a top-level `_cmd_*`
handler taking those four values as explicit parameters instead of
capturing them, and `intercept` itself is now just a lookup over
`_ROUTES` plus the two cases that don't fit a static prefix match
(`@handle` delegation, the unknown-command fallback). A handful of
handlers (`_cmd_history`, `_cmd_config`, `_cmd_model`, `_cmd_vault_ops`,
`_cmd_skills`) were themselves complex enough to need a second level of
case-function extraction, using the same tiered-case pattern used
throughout ADR-124/125 for vault.py/engine.py.
"""

import logging
import os
import re
import shutil
from collections.abc import Callable, Generator
from typing import Any

from sympose.config import DEFAULT_CHAT_MODEL, config_manager
from sympose.mcp import mcp_registry
from sympose.model_capability import clears, strictest_tier, tier_of
from sympose.models import ModelCatalog, get_local_ollama_models
from sympose.sessions import SessionManager
from sympose.skills import skill_manager
from sympose.ui import TerminalUI
from sympose.vault import VaultManager
from sympose.sub_agents import SubAgentEngine, SubAgentTask

log = logging.getLogger(__name__)

_RESET_CHAT_RE = re.compile(
    r"^(?:please\s+)?(?:delete|clear|reset|wipe|start\s+a\s+new)\s+"
    r"(?:our\s+|the\s+|this\s+)?(?:chat|conversation|history|session)$",
    re.IGNORECASE,
)
_RESET_MEMORY_RE = re.compile(
    r"^(?:please\s+)?(?:delete|clear|wipe|reset)\s+(?:your\s+|all\s+)?memory$",
    re.IGNORECASE,
)
_MENTION_RE = re.compile(r"^\s*@(\w+)(?:\s*[:,]?\s*(.*))?$", re.DOTALL)


# --- 0. Setup & Onboarding Wizard -------------------------------------------
def _cmd_setup(engine: Any, handle: str, clean_input: str, profile: dict):
    from sympose.bootstrap import resolve_workspace_dir, run_first_run_onboarding

    workspace_dir = resolve_workspace_dir()
    run_first_run_onboarding(workspace_dir, force=True)
    yield "✨ Setup configuration updated."


# --- 0b. Conversation History & Session Resumption (/history, /sessions) ---
def _resolve_session_match(target_id: str) -> str:
    """Resolves a possibly-truncated session id against the recent list — a
    startswith or substring match, falling back to the raw id itself."""
    all_s = SessionManager.list_sessions(limit=50)
    return next(
        (
            s["session_id"]
            for s in all_s
            if s["session_id"].startswith(target_id) or target_id in s["session_id"]
        ),
        target_id,
    )


def _history_new(engine: Any, handle: str, profile: dict):
    engine.new_session(handle)
    yield f"✨ Started fresh conversation session for {profile.get('name', handle)}."


def _history_delete(target_id: str):
    match = _resolve_session_match(target_id)
    if SessionManager.delete_session(match):
        yield f"🗑️ Deleted session `{match}`."
    else:
        yield f"⚠️ Could not delete session `{target_id}` (not found)."


def _history_view(console: Any, handle: str, target_id: str, show_all: bool):
    match = _resolve_session_match(target_id)
    session = SessionManager.load_session(match)
    if not session:
        yield f"⚠️ Session `{target_id}` not found."
        return
    turns = session.get("turns", [])
    disp_turns = turns if show_all else turns[-6:]
    TerminalUI.render_session_resumed(
        console, session.get("title", ""), session.get("handle", handle), disp_turns
    )
    yield ""


def _history_resume(console: Any, engine: Any, handle: str, target_id: str):
    match = _resolve_session_match(target_id)
    session = engine.resume_session(handle, match)
    if not session:
        yield f"⚠️ Session `{target_id}` not found."
        return
    turns = session.get("turns", [])
    k_turns = int(engine.config.get("performance.resume_context_turns"))
    disp_turns = turns[-k_turns:] if k_turns > 0 else turns
    TerminalUI.render_session_resumed(
        console, session.get("title", ""), session.get("handle", handle), disp_turns
    )
    yield ""


def _history_list(console: Any, engine: Any, handle: str, subcmd: str, parts: list):
    is_all = subcmd in ("all", "--all") or (
        len(parts) > 2 and parts[2] in ("all", "--all")
    )
    target_handle = None if is_all else handle
    active_sid = engine.active_sessions.get(handle.lower())
    sessions = SessionManager.list_sessions(
        handle=target_handle, limit=15, active_session_id=active_sid
    )

    if not sessions:
        yield f"No past conversations found{' for @' + handle if not is_all else ''}."
        return

    chosen_id = TerminalUI.select_session(
        console,
        sessions,
        active_session_id=engine.active_sessions.get(handle.lower()),
        handle=handle if not is_all else None,
        show_handle=is_all,
    )

    if not chosen_id:
        yield "History selection cancelled."
        return

    session = engine.resume_session(handle, chosen_id)
    if session:
        turns = session.get("turns", [])
        k_turns = int(engine.config.get("performance.resume_context_turns"))
        disp_turns = turns[-k_turns:] if k_turns > 0 else turns
        TerminalUI.render_session_resumed(
            console, session.get("title", ""), session.get("handle", handle), disp_turns
        )
        yield ""
    else:
        yield f"⚠️ Could not load session `{chosen_id}`."


def _cmd_history(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split()
    subcmd = parts[1].lower() if len(parts) > 1 else "list"
    console = TerminalUI.get_console()

    if subcmd in ("new", "create"):
        yield from _history_new(engine, handle, profile)
        return
    if subcmd in ("delete", "remove", "rm") and len(parts) > 2:
        yield from _history_delete(parts[2])
        return
    if subcmd in ("view", "show") and len(parts) > 2:
        yield from _history_view(console, handle, parts[2], "--all" in parts)
        return
    if subcmd in ("resume", "load") and len(parts) > 2:
        yield from _history_resume(console, engine, handle, parts[2])
        return
    yield from _history_list(console, engine, handle, subcmd, parts)


# --- 1. Reset / New Session / Delete Conversation ---------------------------
def _cmd_reset(engine: Any, handle: str, clean_input: str, profile: dict):
    engine.reset_history(handle)
    yield f"🧹 Conversation history deleted for {profile.get('name', handle)}. Context refreshed."


# --- 2. Clear Screen & Terminal Session -------------------------------------
def _cmd_clear(engine: Any, handle: str, clean_input: str, profile: dict):
    engine.reset_history(handle)
    yield "CLEARED_SESSION"


# --- 2b. Reset / Wipe Working Memory ----------------------------------------
def _cmd_reset_memory(engine: Any, handle: str, clean_input: str, profile: dict):
    mem_file = profile.get("memory_file", f"profiles/{handle}_memory.md")
    p_name = profile.get("name", handle)
    template_file = f"{mem_file}.example"
    initial_content = f"# {p_name}: Persistent Working Memory\n\n"
    if os.path.exists(template_file):
        try:
            with open(template_file, "r", encoding="utf-8") as tf:
                initial_content = tf.read()
        except Exception as e:
            log.debug(
                "[reset memory] failed to read template %s: %s", template_file, e
            )
    with open(mem_file, "w", encoding="utf-8") as f:
        f.write(initial_content)
    engine.reset_history(handle)
    yield f"🧠 Persistent working memory and active conversation deleted for {p_name}. Reset to clean template."


# --- 3. On-Demand Session Save -----------------------------------------------
def _cmd_save(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split()
    def_t = engine.config.get("session.exit_behavior.default_target")
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


# --- 4. Master Configuration (/config) — schema-driven (see config_schema.py)
def _config_show(cfg: Any, sections: list, global_settings: Callable) -> Generator[str, None, None]:
    out = ["# ⚙️  ACTIVE RUNTIME CONFIGURATION\n"]
    for section in sections:
        rows = [s for s in global_settings() if s.section == section]
        if not rows:
            continue
        out.append(f"\n### {section}")
        for s in rows:
            cur = cfg.get(s.key)
            shown = (
                "(chat model)"
                if s.key.endswith("summarization_model") and not cur
                else ("''" if cur == "" else cur)
            )
            lock = "" if s.live else "  _(restart)_"
            out.append(f"- `{s.key}` = `{shown}` — {s.description}{lock}")
    out.append(
        "\n### 💡  Tuning\n"
        "- `/config set <key> <value>` — change a live knob (persisted to disk)\n"
        "- `/config get <key>` — one key with its default and allowed values\n"
        "- Per-persona knobs (`vault_grounding`, `temperature`, …): `/persona set @<handle> <key> <value>`"
    )
    yield "\n".join(out)


def _config_get(cfg: Any, get_setting: Callable, key: str):
    s = get_setting(key)
    if not s:
        yield f"⚠️ Unknown config key `{key}`. Run `/config` to list them."
        return
    lines = [
        f"### `{key}`",
        f"- **value**: `{cfg.get(key)}`",
        f"- **default**: `{s.default}`",
        f"- **type**: `{s.type}`  •  **scope**: `{s.scope}`  •  **live**: `{s.live}`",
        f"- {s.description}",
    ]
    if s.choices:
        lines.append(f"- **allowed**: {', '.join(map(str, s.choices))}")
    if s.minimum is not None or s.maximum is not None:
        lines.append(f"- **range**: {s.minimum} … {s.maximum}")
    yield "\n".join(lines)


def _config_set(
    engine: Any,
    cfg: Any,
    get_setting: Callable,
    coerce: Callable,
    validate: Callable,
    key: str,
    raw_val: str,
):
    s = get_setting(key)
    if not s:
        yield f"⚠️ Unknown config key `{key}`. Run `/config` to list valid keys."
        return
    if s.scope == "persona":
        yield (
            f"⚠️ `{key}` is a **per-persona** setting — use "
            f"`/persona set @<handle> {key} <value>`, not `/config`."
        )
        return
    try:
        val = coerce(s, raw_val)
    except ValueError as e:
        yield f"⚠️ `{key}`: {e}."
        return
    ok, err = validate(key, val)
    if not ok:
        yield f"⚠️ `{key}`: {err}."
        return
    engine.config.set(key, val)
    engine.config.save()
    if key == "performance.max_context_turns":
        engine.max_turns = int(val)
    restart = "" if s.live else "  (needs a restart to take effect)"
    yield f"✅ `{key}` = `{val}` — persisted to disk.{restart}"


def _cmd_config(engine: Any, handle: str, clean_input: str, profile: dict):
    from sympose.config_schema import (
        SECTIONS,
        coerce,
        get_setting,
        global_settings,
        validate,
    )

    cfg = engine.config
    parts = clean_input.split(maxsplit=3)
    sub = parts[1].lower() if len(parts) > 1 else ""

    if not sub:
        yield from _config_show(cfg, SECTIONS, global_settings)
        return
    if sub == "get" and len(parts) >= 3:
        yield from _config_get(cfg, get_setting, parts[2])
        return
    if sub == "set" and len(parts) >= 4:
        yield from _config_set(
            engine, cfg, get_setting, coerce, validate, parts[2], parts[3]
        )
        return
    yield (
        "Usage:\n"
        "- `/config` — show all settings\n"
        "- `/config get <key>` — inspect one\n"
        "- `/config set <key> <value>` — change a live knob"
    )


# --- 4a-bis. Per-persona knob editor (/persona) -----------------------------
def _cmd_persona(engine: Any, handle: str, clean_input: str, profile: dict):
    from sympose.config_schema import persona_settings

    parts = clean_input.split(maxsplit=4)
    sub = parts[1].lower() if len(parts) > 1 else "show"

    if sub in ("show", "list", ""):
        t_handle = (
            parts[2].replace("@", "").lower() if len(parts) > 2 else handle.lower()
        )
        prof = engine.pm.get_profile(t_handle)
        if not prof:
            yield f"⚠️ Persona `@{t_handle}` not found."
            return
        out = [
            f"# 🎭  PER-PERSONA KNOBS — {prof.get('name', t_handle)} (`@{t_handle}`)\n"
        ]
        for s in persona_settings():
            cur = prof.get(s.key, s.default)
            shown = "(inherit)" if cur in (None, "") else cur
            allowed = f"  _{', '.join(map(str, s.choices))}_" if s.choices else ""
            out.append(f"- `{s.key}` = `{shown}` — {s.description}{allowed}")
        out.append(
            f"\n💡 `/persona set @{t_handle} <key> <value>` — writes `profiles/{t_handle}.yaml`"
        )
        yield "\n".join(out)
        return

    if sub == "set" and len(parts) >= 5:
        t_handle, key, raw_val = (
            parts[2].replace("@", "").lower(),
            parts[3],
            parts[4],
        )
        ok, msg = engine.pm.set_persona_field(t_handle, key, raw_val)
        yield f"✅ {msg}" if ok else f"⚠️ {msg}"
        return

    yield (
        "Usage:\n"
        "- `/persona show [@handle]` — list a persona's knobs\n"
        "- `/persona set @handle <key> <value>` — change one (e.g. `/persona set @sam temperature 0.6`)"
    )


# --- 4b. Render Mode Switcher (/render) -------------------------------------
def _cmd_render(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    current_mode = str(engine.config.get("performance.render_mode")).lower()
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
        "1": "hybrid",
        "hybrid": "hybrid",
        "smart": "hybrid",
        "2": "buffered",
        "buffered": "buffered",
        "full": "buffered",
        "markdown": "buffered",
        "3": "raw",
        "raw": "raw",
        "plain": "raw",
    }
    if sub in mode_map:
        target_mode = mode_map[sub]
        engine.config.set("performance.render_mode", target_mode)
        engine.config.save()
        yield f"✅ Terminal render mode updated to **`{target_mode}`** (persisted to config.yaml)."
    else:
        yield "⚠️ Invalid render mode. Available options: `hybrid`, `buffered`, `raw`."


# --- 5. Explicit /remember --------------------------------------------------
def _cmd_remember(engine: Any, handle: str, clean_input: str, profile: dict):
    fact = clean_input[10:].strip()
    if not fact:
        yield "Usage: `/remember <fact to save>`"
        return
    if engine.pm.append_memory(handle, fact):
        yield f"Saved to {profile.get('name', handle)}'s memory:\n> {fact}"
    else:
        yield f"Error: Failed to save memory to {profile.get('name', handle)}."


# --- 5b. Memory Compactor (/compact) ----------------------------------------
def _cmd_compact(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split()
    target_arg = (
        parts[1].lower().replace("@", "") if len(parts) > 1 else handle.lower()
    )
    from sympose.compactor import MemoryCompactor

    if target_arg in ("shared", "all", "team"):
        shared_file = os.path.join(
            getattr(engine.pm, "profiles_dir", "profiles"), "_shared_memory.md"
        )
        before_count = MemoryCompactor.count_bullet_lines(shared_file)
        yield f"🧹 **Compacting Shared Team Working Memory** (`{shared_file}`, {before_count} entries)..."
        ok = MemoryCompactor.compact_file(shared_file, is_shared=True)
        if ok:
            after_count = MemoryCompactor.count_bullet_lines(shared_file)
            yield f"\n\n✅ **Compaction Complete:** Shared memory consolidated from {before_count} to {after_count} high-density bullets."
        else:
            yield "\n\n⚠️ Compaction failed or memory file is empty."
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
            yield "\n\n⚠️ Compaction failed or memory file is empty."


# --- 6. Model Handler (/model) -----------------------------------------------
def _model_status(engine: Any, handle: str, profile: dict):
    active_override = engine.get_model_override(handle)
    default_model = profile.get("model") or DEFAULT_CHAT_MODEL
    current_model = active_override or default_model

    or_key = (
        "✅ Configured"
        if os.getenv("OPENROUTER_API_KEY")
        else "❌ Missing (add OPENROUTER_API_KEY to .env)"
    )
    gem_key = (
        "✅ Configured"
        if os.getenv("GEMINI_API_KEY")
        else "❌ Missing (add GEMINI_API_KEY to .env)"
    )
    ant_key = (
        "✅ Configured"
        if os.getenv("ANTHROPIC_API_KEY")
        else "❌ Missing (add ANTHROPIC_API_KEY to .env)"
    )
    oai_key = (
        "✅ Configured"
        if os.getenv("OPENAI_API_KEY")
        else "❌ Missing (add OPENAI_API_KEY to .env)"
    )

    state_tag = (
        f"`{current_model}` (Live Session Override)"
        if active_override
        else f"`{current_model}` (Profile Default)"
    )

    local_models = get_local_ollama_models()
    if local_models:
        ollama_lines = [
            f"  - `ollama/{m}` — pulled locally" for m in local_models[:3]
        ]
    else:
        ollama_lines = [
            "  - *None pulled.* `ollama pull <model>` (e.g. `gemma2:9b`), "
            "or `ollama serve` if it's not running."
        ]

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
        *ollama_lines,
        "",
        "### 💡  COMMANDS & NAVIGATION",
        "- Search catalog: `/model find <keyword>` (e.g. `/model find sonnet`, `/model find deepseek`)",
        "- Switch model: `/model <model_id>` (e.g. `/model openrouter/anthropic/claude-3.5-sonnet`)",
        "- Refresh catalog cache: `/model refresh`",
        "- Revert to default model: `/model reset`",
        "- Setup wizard: `/setup`",
    ]
    yield "\n".join(lines)


def _model_find(query: str):
    if not query:
        yield "Usage: `/model find <keyword>` (e.g. `/model find sonnet`, `/model find deepseek`)"
        return
    matches = ModelCatalog.search_models(query, limit=10)
    if matches:
        res = [f"**OpenRouter Models Matching '{query}':**"]
        for m in matches:
            ctx_str = (
                f"({m.get('context_length', 0) // 1000}k ctx)"
                if m.get("context_length")
                else ""
            )
            res.append(
                f"- **`openrouter/{m['id']}`** {ctx_str} — *{m.get('name', '')}*"
            )
        res.append(f"\n*To switch:* `/model openrouter/{matches[0]['id']}`")
        yield "\n".join(res)
    else:
        yield f"No models found matching `{query}` in OpenRouter catalog. Run `/model refresh` to update."


def _model_refresh():
    fresh = ModelCatalog.get_cached_models(force_refresh=True)
    yield f"🔄 **Refreshed OpenRouter Catalog:** {len(fresh)} models indexed in local cache."


def _model_reset(engine: Any, handle: str, profile: dict):
    default_model = profile.get("model") or DEFAULT_CHAT_MODEL
    engine.clear_model_override(handle)
    yield f"Reset model for {profile.get('name', handle)} back to profile default: `{default_model}`."


def _capability_gap_warning(profile: dict, new_model: str) -> str | None:
    """ADR-139: manual `/model` overrides are excluded from every existing
    capability-tier gate (ADR-128's sub-agent wiring, ADR-135's main-turn
    opt-in) — this is the one place that checks an override against the
    same tier ladder those already use, instead of leaving it unchecked.
    Combines every loaded skill's declared `minimum_capability_tier` via
    `strictest_tier` (the same combining rule ADR-139's own Tier-1
    sibling fix uses in `_resolve_target_model`) and reports a concrete
    gap if `new_model`'s own declared tier doesn't clear it. `strict=False`
    always — matches the existing safeguard that no chat-turn-adjacent
    path may raise on a misconfigured tier name."""
    floor = None
    for name in profile.get("skills") or []:
        skill = skill_manager.get_skill(name)
        if skill and skill.minimum_capability_tier:
            floor = strictest_tier(
                config_manager.get("models.capability_tier_order"),
                floor,
                skill.minimum_capability_tier,
            )
    if not floor:
        return None
    tier_order = config_manager.get("models.capability_tier_order")
    tiers = config_manager.get("models.capability_tiers")
    if clears(tier_order, tiers, new_model, floor):
        return None
    return (
        f"\n\n⚠️ *Model `{new_model}` is tier `{tier_of(tier_order, tiers, new_model)}`; "
        f"a loaded skill needs at least `{floor}` — its judgment calls "
        "(e.g. when to fetch from the vault) may be unreliable this session.*"
    )


def _model_set(engine: Any, handle: str, profile: dict, new_model: str):
    engine.set_model_override(handle, new_model)
    msg = (
        f"Model for {profile.get('name', handle)} temporarily "
        f"set to `{new_model}`.\n*(Run `/model reset` to "
        "restore default)*"
    )
    is_local_override = new_model.startswith("ollama/") or ":11434" in str(
        profile.get("api_base", "")
    )
    if is_local_override and profile.get("vault_folders"):
        msg += (
            "\n\n⚠️ *Manual overrides aren't second-guessed — "
            "this persona's vault-recall/sub-agent grounding "
            "guard normally avoids routing that work to a "
            "local model, but this override skips it.*"
        )
    capability_gap = _capability_gap_warning(profile, new_model)
    if capability_gap:
        msg += capability_gap
    yield msg


def _cmd_model(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split(maxsplit=1)
    sub = parts[1].strip() if len(parts) > 1 else ""
    sub_lower = sub.lower()

    if not sub or sub_lower in ("list", "help", "status", "ls"):
        yield from _model_status(engine, handle, profile)
    elif sub_lower.startswith(("find ", "search ")):
        query = sub.split(maxsplit=1)[1].strip() if len(sub.split()) > 1 else ""
        yield from _model_find(query)
    elif sub_lower == "refresh":
        yield from _model_refresh()
    elif sub_lower == "reset":
        yield from _model_reset(engine, handle, profile)
    else:
        yield from _model_set(engine, handle, profile, sub)


# --- 6. Sandboxed Vault & Markdown Explorer (/vault, /read, /view, /open, /backlinks)
def _vault_backlinks(profile: dict, raw: str):
    target = (
        raw[16:].strip() if raw.startswith("/vault backlinks") else raw[10:].strip()
    )
    if not target:
        yield "Usage: `/vault backlinks <note_name>` or `/backlinks <note_name>`"
        return
    yield VaultManager.get_backlinks_digest(profile, target)


def _vault_open(profile: dict, raw: str):
    target = raw[12:].strip() if raw.startswith("/vault open ") else raw[6:].strip()
    if not target:
        yield "Usage: `/open <#|note_name>` or `/vault open <#|note_name>`"
        return
    ok, msg = VaultManager.open_in_obsidian(profile, target)
    yield f"✨ {msg}" if ok else f"⚠️ {msg}"


def _vault_read(profile: dict, console: Any, raw: str):
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
            TerminalUI.interactive_vault_browser(
                console, profile, "Search", cached, initial_index=int(target)
            )
        else:
            TerminalUI.render_vault_note_panel(
                console, rel_path, content, abs_path=abs_path
            )
        yield ""
    else:
        yield f"### 📄 Note: `{rel_path}`\n\n{content}"


def _vault_show_previous(profile: dict, console: Any):
    cached = VaultManager.get_last_search(profile)
    if not cached:
        yield "No previous search results found in session. Run `/vault <query>` to search."
        return
    if console:
        TerminalUI.interactive_vault_browser(
            console, profile, "Previous Search", cached
        )
        yield ""
    else:
        yield VaultManager.format_search_digest("Previous Search", cached)


def _vault_query_index(profile: dict, console: Any, cached: list, idx: int):
    if console:
        TerminalUI.interactive_vault_browser(
            console, profile, "Search", cached, initial_index=idx
        )
        yield ""
    else:
        item = cached[idx - 1]
        content = VaultManager.read_note(profile, item["rel_path"])
        yield f"### 📄 Note: `{item['rel_path']}`\n\n{content}"


def _vault_query(profile: dict, console: Any, raw: str):
    query = raw[7:].strip() if raw.startswith("/vault ") else raw[6:].strip()
    if not query:
        cached = VaultManager.get_last_search(profile)
        if cached and console:
            TerminalUI.interactive_vault_browser(
                console, profile, "Previous Search", cached
            )
            yield ""
        else:
            yield "Usage: `/vault <query>` or `/vault backlinks <note>` or `/vault back`"
        return

    cached = VaultManager.get_last_search(profile)
    if query.isdigit() and cached:
        idx = int(query)
        if 1 <= idx <= len(cached):
            yield from _vault_query_index(profile, console, cached, idx)
            return

    results = VaultManager.search_structured(profile, query)
    if console:
        TerminalUI.interactive_vault_browser(console, profile, query, results)
        yield ""
    else:
        yield VaultManager.format_search_digest(query, results)


def _cmd_vault_ops(engine: Any, handle: str, clean_input: str, profile: dict):
    raw = clean_input.strip()
    console = TerminalUI.get_console()

    if raw.startswith("/vault backlinks") or raw.startswith("/backlinks"):
        yield from _vault_backlinks(profile, raw)
        return
    if raw.startswith("/vault open ") or raw.startswith("/open "):
        yield from _vault_open(profile, raw)
        return
    if raw.startswith(("/read ", "/view ", "/vault read ")):
        yield from _vault_read(profile, console, raw)
        return
    if raw in ("/vault", "/vaults", "/vault back", "/vault list", "/vault prev"):
        yield from _vault_show_previous(profile, console)
        return
    yield from _vault_query(profile, console, raw)


def _cmd_note(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input[6:].strip().split(maxsplit=1)
    yield (
        VaultManager.write_note(profile, parts[0], parts[1])
        if len(parts) >= 2
        else "Usage: `/note <file.md> <content>`"
    )


def _cmd_daily(engine: Any, handle: str, clean_input: str, profile: dict):
    yield (
        VaultManager.write_daily_note(profile, clean_input[7:].strip())
        if clean_input[7:].strip()
        else "Usage: `/daily <reflection>`"
    )


def _cmd_ask(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input[5:].strip().split(maxsplit=1)
    if len(parts) < 2:
        yield "Usage: `/ask <@persona> <task>`"
        return
    target = parts[0].replace("@", "").lower()
    target_p = engine.pm.get_profile(target)
    if not target_p:
        yield f"Specialist persona `@{target}` not found."
        return
    yield f"[Delegating to {target_p.get('name', target)} ({target_p.get('title', 'Specialist')}):]\n\n"
    for chunk in engine.consult_persona(target, parts[1]):
        yield chunk


# --- 7. Skills & MCP Inspection & Management (/skill, /skills, /tools) -----
def _skill_show(parts: list):
    if len(parts) < 3:
        yield "Usage: `/skill show <skill_name>` (e.g. `/skill show git_workflow`)"
        return
    s_name = parts[2].lower()
    skill = skill_manager.get_skill(s_name)
    if not skill:
        yield f"⚠️ Skill `{s_name}` not found. Run `/skill list` to see all available skills."
        return
    tags_str = f"- **Tags:** `{', '.join(skill.tags)}`\n" if skill.tags else ""
    mcp_str = (
        f"- **MCP Dependencies:** `{', '.join(skill.mcp_servers)}`\n"
        if skill.mcp_servers
        else ""
    )
    models_str = (
        f"- **Recommended Models:** `{', '.join(skill.recommended_models)}`\n"
        if skill.recommended_models
        else ""
    )
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
        f"*To mount to specific persona:* `/skill add {skill.name} @<handle>`"
    )


def _skill_add(engine: Any, handle: str, parts: list):
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


def _skill_remove(engine: Any, handle: str, parts: list):
    if len(parts) < 3:
        yield "Usage: `/skill remove <skill_name> [@handle]`\nExample: `/skill remove git_workflow @rosalind`"
        return
    s_name = parts[2].lower()
    t_handle = parts[3].replace("@", "").lower() if len(parts) > 3 else handle.lower()
    ok, msg = engine.pm.update_persona_skills(t_handle, s_name, action="remove")
    yield f"✅ {msg}" if ok else f"⚠️ {msg}"


def _skill_direct(direct_skill: Any):
    tags_str = (
        f"- **Tags:** `{', '.join(direct_skill.tags)}`\n" if direct_skill.tags else ""
    )
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
        f"*To mount to specific persona:* `/skill add {direct_skill.name} @<handle>`"
    )


def _skill_list_all(engine: Any, handle: str, profile: dict):
    loaded_skills = skill_manager.list_skills()
    engine.pm.reload_profiles()
    equipped_map: dict[str, list] = {}
    for p_h, p_data in engine.pm.profiles.items():
        for sk in p_data.get("skills") or []:
            equipped_map.setdefault(sk.lower(), []).append(f"@{p_h}")

    curr_skills = profile.get("skills") or []
    curr_sk_str = (
        ", ".join(f"`{s}`" for s in curr_skills) if curr_skills else "*None*"
    )

    lines = [
        "# 🛠️  INSTALLED SKILLS & MCP TOOL SERVERS\n",
        f"### 👤  ACTIVE PERSONA: {profile.get('name', handle)} (`@{handle}`)",
        f"- **Equipped Skills:** {curr_sk_str}\n",
        "### 📦  AVAILABLE PROCEDURAL SKILL PLAYBOOKS (`skills/`)",
    ]
    if loaded_skills:
        for s in loaded_skills:
            eq_list = equipped_map.get(s["name"].lower(), [])
            eq_str = f" *(Equipped: {', '.join(eq_list)})*" if eq_list else ""
            lines.append(
                f"- **`{s['name']}`**: {s['title']} — *{s['description'] or 'No description'}*{eq_str}"
            )
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
    lines.append("- Mount skill to active persona: `/skill add <skill_name>`")
    lines.append(
        "- Mount skill to specific persona: `/skill add <skill_name> @<handle>`"
    )
    lines.append(
        "- Unmount skill from persona: `/skill remove <skill_name> [@handle]`"
    )
    lines.append("- Inspect playbook directives: `/skill show <skill_name>`")
    lines.append("- Run one-off task with skill: `/subagent <skill_name> <task prompt>`")

    yield "\n".join(lines)


def _cmd_skills(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input.split()
    sub = parts[1].lower() if len(parts) > 1 else "list"

    if sub in ("show", "view", "info"):
        yield from _skill_show(parts)
        return
    if sub in ("add", "mount", "install"):
        yield from _skill_add(engine, handle, parts)
        return
    if sub in ("remove", "unmount", "uninstall", "rm"):
        yield from _skill_remove(engine, handle, parts)
        return
    if sub not in ("list", "ls") and (direct_skill := skill_manager.get_skill(sub)):
        yield from _skill_direct(direct_skill)
        return
    yield from _skill_list_all(engine, handle, profile)


# --- 8. Ephemeral Sub-Agent Dispatch (/subagent) ----------------------------
def _cmd_sub_agent(engine: Any, handle: str, clean_input: str, profile: dict):
    parts = clean_input[10:].strip().split(maxsplit=1)
    if len(parts) < 2:
        yield "Usage: `/subagent <skill_or_mcp> <task prompt>`\nExample: `/subagent git_workflow summarize uncommitted git diffs`"
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

    task = SubAgentTask(
        task_prompt=task_prompt,
        skills=skills_to_load,
        mcp_servers=mcp_to_load,
        parent_agent=handle,
    )
    yield f"🛠️ **Dispatching Ephemeral Sub-Agent** (Skills: `{skills_to_load}`, MCP: `{mcp_to_load}`)...\n\n"
    for chunk in SubAgentEngine.execute_sub_agent_stream(task):
        yield chunk


# --- 9. Explicit @mention delegation (must start with @<handle>) -----------
def _cmd_mention(engine: Any, target_tag: str, delegated_prompt: str):
    target_p = engine.pm.get_profile(target_tag)
    yield f"[Delegating to {target_p.get('name', target_tag)} ({target_p.get('title', 'Specialist')}):]\n\n"
    for chunk in engine.consult_persona(target_tag, delegated_prompt):
        yield chunk


def _try_mention(engine: Any, handle: str, clean_input: str):
    mention_match = _MENTION_RE.match(clean_input)
    if not mention_match:
        return None
    target_tag = mention_match.group(1).lower()
    delegated_prompt = (mention_match.group(2) or "").strip() or clean_input
    if target_tag not in engine.pm.profiles or target_tag == handle.lower():
        return None
    return _cmd_mention(engine, target_tag, delegated_prompt)


# --- 10. Delete / Retire Persona --------------------------------------------
def _cmd_delete(engine: Any, handle: str, clean_input: str, profile: dict):
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
            except Exception as e:
                log.debug("Failed to archive %s to %s: %s", src, dst, e)
        engine.pm.reload_profiles()
        if engine.config.get("runtime.default_persona") == t_handle:
            engine.config.set("runtime.default_persona", "samantha")
            engine.config.save()
        yield f"🗄️ **Retired persona @{t_handle}**. Files safely archived to `{arch_dir}/`."
    else:
        engine.pm.reload_profiles()
        yield f"⚠️ Persona `@{t_handle}` not found in `{p_dir}/`."


# --- 11. Help Menu -----------------------------------------------------------
def _cmd_help(engine: Any, handle: str, clean_input: str, profile: dict):
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
        "- `/vault backlinks <note>` or `/backlinks <note>` — Inspect incoming references for a note\n"
        "- `/read <#>` · `/view <#>` · `/open <#>` — Open a search result in terminal / Obsidian\n"
        "- `/note <file.md> <content>` — Create or append to a sandboxed note\n"
        "- `/daily <reflection>` — Append reflection to today's Daily Note\n"
        "- `/remember <fact>` — Save fact into persona's persistent memory\n"
        "- `/compact [shared|@handle]` — Consolidate duplicate memory bullets\n"
        "- `/save [memory|obsidian|both]` — Manually trigger session summary\n\n"
        "### 🛠️  SUB-AGENTS & TOOLS\n"
        "- `/skills` or `/skill [list]` — Inspect indexed skill playbooks and active mounts\n"
        "- `/skill add <name> [@handle]` — Mount skill to active persona (or @handle)\n"
        "- `/skill remove <name> [@handle]` — Unmount skill from persona\n"
        "- `/skill show <name>` — Inspect playbook directives & markdown source\n"
        "- `/subagent <skill|mcp> <task>` — Dispatch ephemeral sub-agent\n"
        "- `/ask <@handle> <task>` — Delegate isolated sub-task to a peer\n\n"
        "### ⚙️  RUNTIME SETTINGS\n"
        "- `/render [hybrid|buffered|raw]` — Switch terminal render mode (interactive menu or direct)\n"
        "- `/config` — View active runtime settings & performance knobs\n"
        "- `/config set <key> <val>` — Live-tune knobs (e.g. `/config set performance.max_context_turns 20`)\n"
        "- `/persona [show|set] @<handle> <key> <val>` — View or set a persona's own knobs (e.g. `temperature`, `local_model`)\n"
        "- `/delete @<handle>` — Safely archive & retire a persona\n"
        "- `/help` or `/commands` — Show this command reference"
    )


# --- 12. Unknown slash command → a helper line, not a prompt to the model. --
def _cmd_unknown(token: str, known: list):
    near = [c for c in known if len(token) >= 2 and c.startswith(token[:3])]
    hint = f" Did you mean: {', '.join(near)}?" if near else ""
    yield f"⚠️ Unknown command `{token}`.{hint}  Run `/commands` for the full list."


def _handle_unknown_command(clean_input: str):
    token = clean_input.split(maxsplit=1)[0].lower()
    from sympose.completer import SymposeCompleter

    known = sorted(c for c in SymposeCompleter.ROOT_COMMANDS if c.startswith("/"))
    if token in known:
        return None
    return _cmd_unknown(token, known)


# Route table: (predicate over the normalized clean_input, handler taking
# (engine, handle, clean_input, profile)) — order mirrors the original
# sequential if-chain; entries are mutually exclusive by prefix, so the
# @mention and unknown-command cases (handled separately below, neither
# sharing a prefix with any route here) can be tried in any position
# relative to this list without changing what matches.
_ROUTES: list[tuple[Callable[[str], bool], Callable]] = [
    (lambda s: s in ("/setup", "/onboard", "/wizard"), _cmd_setup),
    (lambda s: s.startswith(("/history", "/sessions")), _cmd_history),
    (lambda s: s in ("/reset", "/new") or bool(_RESET_CHAT_RE.search(s)), _cmd_reset),
    (lambda s: s in ("/clear", "/cls"), _cmd_clear),
    (
        lambda s: s in ("/reset memory", "/clear memory")
        or bool(_RESET_MEMORY_RE.search(s)),
        _cmd_reset_memory,
    ),
    (lambda s: s.startswith("/save"), _cmd_save),
    (lambda s: s.startswith("/config"), _cmd_config),
    (lambda s: s == "/persona" or s.startswith("/persona "), _cmd_persona),
    (lambda s: s == "/render" or s.startswith("/render "), _cmd_render),
    (lambda s: s.startswith("/remember "), _cmd_remember),
    (lambda s: s == "/compact" or s.startswith("/compact "), _cmd_compact),
    (lambda s: s == "/model" or s.startswith("/model "), _cmd_model),
    (
        lambda s: s.startswith(("/vault", "/backlinks", "/read", "/view", "/open")),
        _cmd_vault_ops,
    ),
    (lambda s: s.startswith("/note "), _cmd_note),
    (lambda s: s.startswith("/daily "), _cmd_daily),
    (lambda s: s.startswith("/ask "), _cmd_ask),
    (lambda s: s.startswith(("/skill", "/skills", "/tools")), _cmd_skills),
    (lambda s: s.startswith("/subagent "), _cmd_sub_agent),
    (lambda s: s.startswith(("/delete", "/retire")), _cmd_delete),
    (lambda s: s in ("/help", "/commands", "/cmds", "/?"), _cmd_help),
]


class CommandInterceptor:
    """Intercepts tactical slash commands and natural memory capture."""

    @staticmethod
    def intercept(
        engine: Any, handle: str, clean_input: str
    ) -> Generator[str, None, None] | None:
        """Checks if input matches a slash/exclamation command or natural intent, returning a generator if so."""
        profile = engine.pm.get_profile(handle)
        if not profile:
            return None

        if clean_input.startswith("!"):
            clean_input = "/" + clean_input[1:]

        for matches, handler in _ROUTES:
            if matches(clean_input):
                return handler(engine, handle, clean_input, profile)

        mention_gen = _try_mention(engine, handle, clean_input)
        if mention_gen is not None:
            return mention_gen

        if clean_input.startswith("/"):
            return _handle_unknown_command(clean_input)

        return None
