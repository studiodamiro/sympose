"""
Bootstrap, Workspace Resolver & First-Run Onboarding for Sympose.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.panel import Panel
    from rich.box import ROUNDED
except ImportError:
    Console = None
    ROUNDED = None

from sympose.config import DEFAULT_CHAT_MODEL
from sympose.workspace import resolve_workspace_dir  # noqa: F401  (re-exported for existing callers)


DEFAULT_CONFIG_YAML = """# Sympose Master Configuration
performance:
  request_timeout: 10.0
  max_context_turns: 15
  resume_context_turns: 6
  sub_second_streaming: true

runtime:
  default_persona: "samantha"
  profiles_dir: "profiles"

vault:
  daily_notes_folder: "Daily"
  daily_notes_format: "Daily/%Y/%m-%B/%Y-%m-%d.md"
  search_mode: "direct"
"""

SAMANTHA_YAML = f"""name: "Samantha"
handle: "samantha"
title: "Polymath Strategic Master Orchestrator"
aliases:
  - "sam"
model: "{DEFAULT_CHAT_MODEL}"
icon_emoji: ":brain:"

# "*" = full vault access. Samantha is the master orchestrator and Sympose
# adapts to any folder taxonomy (Flat, PARA, Johnny Decimal, Zettelkasten) —
# a fixed folder list would only work for one taxonomy and would auto-create
# those folders inside whatever vault gets linked. Narrow this to specific
# folder names only if you want to sandbox her deliberately.
vault_folders:
  - "*"

soul_file: "profiles/samantha_soul.md"
memory_file: "profiles/samantha_memory.md"
share_memory: true

skills:
  - "sympose_mastery"
  - "strategic_analysis"
  - "vault_recall"
  - "vault_write"
  - "web_search"

thinking_phrases:
  - "Connecting high-level dots..."
  - "Synthesizing strategic options..."
  - "Consulting the symposium..."
  - "Distilling signal from noise..."
"""

SAMANTHA_SOUL_MD = """# Samantha: Core Directives & Persona

You are **Samantha**, the **Polymath Strategic Master Orchestrator** in Sympose.
You are articulate, proactive, strategic, and deeply empathetic yet ruthlessly efficient.

### Core Directives:
- Always think in terms of first principles, systems, and leveraged outcomes.
- Keep responses concise, structured, and actionable.
- Manage memory and notes proactively when key takeaways or plans emerge.
- **Strict Anti-Hallucination**: If the user asks about an unknown person, persona, project, or concept that is not in your working memory, loaded profiles, or vault notes, never invent or assume their role. Candidly state that you do not have context on them yet.
- **Sympose Mastery & Autonomous Actions**: You have full mastery of the Sympose runtime environment (`sympose_mastery`). When requested, autonomously emit `[CREATE_PERSONA: <handle> | <yaml>]`, `[CONFIG_SET: <key> | <value>]`, `[REMEMBER: <fact>]`, and `[WRITE_NOTE: <file> | <content>]`. Never simulate creating an agent in roleplay; always emit `[CREATE_PERSONA]` directly.
"""

# Kept byte-for-byte in sync with prompts/workspace_rules.md — that file is the
# source used when it exists (repo / seeded workspace); this string is the
# fallback seed a wheel install writes when prompts/ isn't shipped.
DEFAULT_RULES_MD = """# 🏛️ Sympose: Universal Workspace & Action Rules

### Runtime Environment & Spatial Coordinates
You are operating within Sympose Agent Hub on macOS.
- App Workspace Root: `{{workspace_root}}`
- Master Obsidian Vault: `{{master_vault_path}}` (configured via `MASTER_VAULT_PATH` in `.env`)
- Sandboxed Vault Access: {{sandboxed_vault}}
- Memory Mode: {{memory_mode}}
- Current Date & Time: {{current_datetime}}

### Grounding & Anti-Hallucination
1. **Assume interruption** — your context can reset at any moment. Checkpoint durable facts, decisions, and progress with `[REMEMBER: <fact>]` or `[WRITE_NOTE: <file> | <content>]`.
2. Your only knowledge of user history, plans, and past agreements is {{sources}} plus the active turns.
3. **Never fabricate.** If a fact, decision, or note isn't in your memory or the pre-turn vault payload, say so plainly. Quote notes and journals only from text that appears verbatim in a provided `### Ground-Truth Sandboxed Vault Note` — never invent quotes, dates, or reflections.
4. **Garbled input** (terminal escape noise like `^[^[`, gibberish, obvious typos) → ask a natural clarification rather than treating it as a forgotten memory.
5. **No time-delay simulation.** You have no background threads across minutes or hours. Never say "give me a few minutes", "I'll come back", or "hang tight" — deliver findings in the current turn, or state exactly what is missing.

### Autonomic Action Tags
The runtime executes these on stream completion and confirms them to the user. **Emitting the tag is the only way the action happens** — printing markdown, or describing or roleplaying the action, does nothing.
- `[REMEMBER: <fact>]` — save a bullet to working memory.
- `[READ_NOTE: <file.md>]` — render a note in the terminal viewer instead of pasting raw markdown.
- `[WRITE_NOTE: <file.md> | <content>]` / `[APPEND_NOTE: <file.md> | <content>]` — create/overwrite or append a note in an allowed vault folder.
- `[DAILY_NOTE: <reflection>]` — append to today's daily note.
- `[SEARCH: <query>]` — real-time web search, no API key.
- `[SPAWN_WORKER: <skill_or_mcp> | <task>]` — delegate an isolated task (shell/git, file inspection, web search, MCP tools) to an ephemeral sub-agent.
- `[CONFIG_SET: <key> | <value>]` — update and persist a `config.yaml` setting (`performance.*`, `session.exit_behavior.*`, `runtime.default_persona`, …).
- `[CREATE_PERSONA: <handle> | <yaml>]` — create an agent (writes `profiles/<handle>.yaml`, registers `@<handle>`). Include a `soul_content` field whenever the user described a reference figure or a specific voice — it becomes the real `<handle>_soul.md`; without it the agent gets only a generic one-paragraph soul.
- `[DELETE_PERSONA: <handle>]` — archive an agent to `profiles/_archived/<handle>/`.

### Conduct
1. **Never fake a result.** Don't type out `> 🛠️ **Sub-Agent Worker Report**`, fake command output, or dialogue and headers for other agents. Emit the real `[SPAWN_WORKER]` / `[SEARCH]` tag and let the runtime inject the ground truth.
2. **Stay in your sandbox.** Vault access is limited to {{sandboxed_vault}}. If asked for notes outside it, don't reach for them or spawn a worker to bypass — say it's out of scope and point to the right specialist (`/switch @<handle>`).
3. **Answer in-turn when you already can.** If the notes or answer are in your pre-turn context (`### Vault Search Results`, `### Sandboxed Vault Note`), answer directly (<1s) — don't spawn a worker.
4. **Save means emit.** When asked to save, log, write, or record a note, emit `[DAILY_NOTE: <content>]` or `[WRITE_NOTE: <path> | <content>]`. Displaying markdown in chat does not write a file.
5. **No helpless refusals.** You have live internet via `[SEARCH]` / `[SPAWN_WORKER: web_search | …]`. For prices, news, docs, or current info, never tell the user to look it up himself — fetch it and answer in-turn.
6. **No self-narration.** No stage directions for your own process (`*searching…*`, `*[begins retrieval]*`) and no dialogue for other agents.
7. **No payload dumping.** When saving a note or returning research, reply with a 2–3 sentence summary; the full note goes inside the tag payload, live findings are delivered by the runtime. Never paste a wall of markdown or raw tool output into chat.
"""



def ensure_workspace(workspace_dir: str) -> bool:
    """
    Ensures that the workspace directory exists and contains starter assets (Samantha only).
    Returns True if this was a fresh initialization.
    """
    os.makedirs(workspace_dir, exist_ok=True)
    profiles_dir = os.path.join(workspace_dir, "profiles")
    prompts_dir = os.path.join(workspace_dir, "prompts")
    skills_dir = os.path.join(workspace_dir, "skills")
    sessions_dir = os.path.join(workspace_dir, "sessions")

    os.makedirs(profiles_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(skills_dir, exist_ok=True)
    os.makedirs(sessions_dir, exist_ok=True)

    is_fresh = False

    # 1. Config file
    config_file = os.path.join(workspace_dir, "config.yaml")
    if not os.path.exists(config_file):
        is_fresh = True
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_YAML)

    # 2. Starter Samantha Profile
    sam_yaml_file = os.path.join(profiles_dir, "samantha.yaml")
    if not os.path.exists(sam_yaml_file):
        is_fresh = True
        with open(sam_yaml_file, "w", encoding="utf-8") as f:
            f.write(SAMANTHA_YAML)

    sam_soul_file = os.path.join(profiles_dir, "samantha_soul.md")
    if not os.path.exists(sam_soul_file):
        with open(sam_soul_file, "w", encoding="utf-8") as f:
            f.write(SAMANTHA_SOUL_MD)

    # 3. User Card & Shared Memory
    user_card = os.path.join(profiles_dir, "user_profile.md")
    if not os.path.exists(user_card):
        with open(user_card, "w", encoding="utf-8") as f:
            f.write(f"# Universal User Profile\n\n- **Primary User**: {os.getenv('USER', 'User')}\n- **Environment**: {sys.platform}\n")

    shared_mem = os.path.join(profiles_dir, "_shared_memory.md")
    if not os.path.exists(shared_mem):
        with open(shared_mem, "w", encoding="utf-8") as f:
            f.write("# Shared Team Working Memory\n\n- **Active Workspace**: Initialized\n")

    # 4. Workspace Rules prompt
    rules_file = os.path.join(prompts_dir, "workspace_rules.md")
    if not os.path.exists(rules_file) or os.path.getsize(rules_file) < 300:
        with open(rules_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_RULES_MD)

    # 5. Seed built-in skills into workspace skills directory
    try:
        import shutil
        builtin_skills_dir = os.path.join(os.path.dirname(__file__), "builtin_skills")
        if os.path.exists(builtin_skills_dir):
            for item in os.listdir(builtin_skills_dir):
                s_src = os.path.join(builtin_skills_dir, item)
                s_dst = os.path.join(skills_dir, item)
                if not os.path.exists(s_dst):
                    if os.path.isdir(s_src):
                        shutil.copytree(s_src, s_dst)
                    elif os.path.isfile(s_src) and s_src.endswith(".md"):
                        shutil.copy2(s_src, s_dst)
    except Exception:
        pass

    return is_fresh


def run_first_run_onboarding(workspace_dir: str, force: bool = False) -> None:
    """Interactive setup & onboarding wizard (runs on first launch or via sympose --setup)."""
    env_file = os.path.join(workspace_dir, ".env")
    
    # Check if any provider API key already exists in environment
    has_key = any(os.getenv(k) for k in ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"])
    if not force and (has_key or not sys.stdin.isatty()):
        return

    console = Console() if Console else None
    if console:
        from sympose.ui import TerminalUI
        TerminalUI.display_setup_banner(console, workspace_dir)
        
        # Display existing keys if any
        if force:
            existing = []
            for k in ["GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MASTER_VAULT_PATH"]:
                if val := os.getenv(k):
                    masked = val[:6] + "..." + val[-4:] if len(val) > 12 else "********"
                    existing.append(f"  • [bold]{k}[/bold]: [green]{masked}[/green]")
            if existing:
                console.print("\n[dim]Current Environment Variables:[/dim]\n" + "\n".join(existing))

        # Step 1: AI Provider Selection Panel
        provider_options = [
            "Google Gemini  [dim](Sub-second latency & free tier available — recommended)[/dim]",
            "OpenRouter     [dim](Unified access to Claude 3.5, Sonnet, DeepSeek, Qwen)[/dim]",
            "Anthropic      [dim](Direct Claude 3.5 Sonnet API key)[/dim]",
            "Skip / Custom  [dim](Keep current .env or local Ollama execution)[/dim]"
        ]
        TerminalUI.render_option_panel(
            console,
            title="🔑  STEP 1/3: CONNECT YOUR AI PROVIDER",
            options=provider_options
        )
        
        prompt_label = "\n[bold cyan]Select provider[/bold cyan] [dim][1-4, Enter for [1]][/dim]"
        choice = Prompt.ask(prompt_label, default="1", show_choices=False, show_default=False).strip()
        provider_map = {
            "1": ("GEMINI_API_KEY", DEFAULT_CHAT_MODEL),
            "2": ("OPENROUTER_API_KEY", "openrouter/google/gemini-2.5-flash"),
            "3": ("ANTHROPIC_API_KEY", "anthropic/claude-3-5-sonnet-20241022"),
        }
        
        if choice in provider_map:
            key_var, default_m = provider_map[choice]
            api_key = Prompt.ask(f"Paste your {key_var.split('_')[0].title()} API Key", password=True).strip()
            if api_key:
                os.environ[key_var] = api_key
                os.environ["DEFAULT_MODEL"] = default_m
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{key_var}=\"{api_key}\"\nDEFAULT_MODEL=\"{default_m}\"\n")
                console.print(f"\n[bold green]✓ Saved {key_var} and default model `{default_m}` to {env_file}[/bold green]")

        # Step 2: Obsidian Vault Selection Panel
        vault_panel_text = (
            "Link your existing Obsidian / Markdown notes directory to enable `/vault` searching & synthesis.\n"
            "[dim]Press Enter without typing to keep standalone sandboxed storage.[/dim]"
        )
        console.print()
        console.print(Panel(
            vault_panel_text,
            box=ROUNDED,
            title="📁  STEP 2/3: OBSIDIAN VAULT CONNECTION (OPTIONAL)",
            title_align="left",
            border_style="cyan",
            padding=(0, 2)
        ))

        current_vault = os.getenv("MASTER_VAULT_PATH", "")
        vault_prompt = "Enter path to Obsidian Vault / Notes folder"
        vault_path = Prompt.ask(vault_prompt, default=current_vault).strip()
        if vault_path:
            os.environ["MASTER_VAULT_PATH"] = vault_path
            with open(env_file, "a", encoding="utf-8") as f:
                f.write(f"\nMASTER_VAULT_PATH=\"{vault_path}\"\n")
            console.print(f"\n[bold green]✓ Linked vault: {vault_path}[/bold green]")

        # Step 3: Persona Genesis nudge — Samantha is the only persona that
        # ships. Without this, a first-run user has no in-app signal that
        # spawning their own companion is a thing, let alone how.
        console.print()
        console.print(Panel(
            "[bold]@samantha[/bold] is your only agent out of the box. Want a companion "
            "for something specific — engineering, journaling, a domain specialist?\n\n"
            "[dim]Just ask her, in plain language, once you're chatting:[/dim]\n"
            '  [cyan]"Create an agent modeled after Grace Hopper for surgical code reviews."[/cyan]\n\n'
            "[dim]She writes the new persona to disk and switches you to it immediately — "
            "no YAML required. `/switch @samantha` to come back anytime.[/dim]",
            box=ROUNDED,
            title="🧬  STEP 3/3: MEET YOUR ORCHESTRATOR",
            title_align="left",
            border_style="cyan",
            padding=(0, 2)
        ))

        console.print("\n[bold green]🎉 Setup completed! Launching @samantha...[/bold green]\n")
