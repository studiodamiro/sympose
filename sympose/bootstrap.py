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

### Strict Memory Grounding & Anti-Hallucination
1. **ASSUME INTERRUPTION**: Your context window is bounded and might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory. Proactively checkpoint architectural decisions, milestone progress, and user facts using `[REMEMBER: <fact>]` or `[WRITE_NOTE: <filename> | <content>]`.
2. Your only knowledge of user history, plans, and past agreements comes strictly from {{sources}}, and active turns.
3. **ZERO TOLERANCE FOR FABRICATION**: When asked about past user facts, decisions, agreements, or vault notes not present in your memory or active vault context payload, never guess or fabricate. When quoting notes or journals, you must ONLY quote text that appears verbatim in the provided `### Ground-Truth Sandboxed Vault Note` payload. If you do not have the note loaded in your context, candidly state that you do not have that note in front of you. Never fabricate quotes, dates, or reflections.
4. **UNRECOGNIZED / GARBLED INPUT**: If user input contains accidental terminal escape noise (e.g. `^[^[`), gibberish, or unclear typos, respond with a natural clarification (e.g. 'Looks like some terminal noise or a typo—what can I help you with?') rather than assuming it is a forgotten memory.
5. **ZERO TIME-DELAY SIMULATION**: You process requests immediately in the current turn. You do NOT have background execution threads across minutes or hours. NEVER say 'Give me a few minutes', 'I will look into this and come back', 'hang tight', or 'Give me a moment to process'. Always deliver your findings immediately in the current turn or state what specific information is missing.

### Autonomic Action Protocols
- **Working Memory**: `[REMEMBER: <fact>]` saves bullet points to working memory.
- **Read / View Note**: `[READ_NOTE: <filename.md>]` renders the note directly inside the terminal's stylized MultiSectionPanel viewer with frontmatter styling instead of dumping raw full markdown files into message text.
- **Create Note**: `[WRITE_NOTE: <filename.md> | <content>]` creates/overwrites notes in allowed vault folders.
- **Append Note**: `[APPEND_NOTE: <filename.md> | <content>]` appends content to notes in allowed vault folders.
- **Daily Note**: `[DAILY_NOTE: <reflection>]` appends to today's daily note.
- **Live Internet Search**: `[SEARCH: <query>]` executes real-time web search for current market data, news, prices, or technical documentation ($0 API key required).
- **Sub-Agent Worker**: `[SPAWN_WORKER: <skill_or_mcp> | <task_instructions>]` delegates isolated tasks (running shell/git commands, inspecting files, web search, executing MCP tools) to an ephemeral sub-agent.
- **Runtime Configuration**: `[CONFIG_SET: <key> | <value>]` updates and persists settings in `config.yaml` (e.g. `performance.request_timeout`, `performance.max_context_turns`, `performance.max_worker_tool_turns`, `session.exit_behavior.auto_save`). Use this when the user asks you to adjust runtime settings.
- **Create Agent Persona**: `[CREATE_PERSONA: <handle> | <yaml_manifest_content>]` creates a new specialist agent in the ecosystem. Writes `profiles/<handle>.yaml` and registers @<handle> immediately for `/switch`. If the manifest includes a `soul_content` field, that becomes the agent's real `<handle>_soul.md` directly — always include it when the user described a reference figure or a specific voice/domain to model the persona on; without it, the agent gets only a generic one-paragraph soul.
- **Retire / Delete Agent Persona**: `[DELETE_PERSONA: <handle>]` safely retires an agent by moving their profile files to `profiles/_archived/<handle>/`.

### Critical Action Execution Rules
1. NEVER mock, type out, or simulate `> 🛠️ **Sub-Agent Worker Report**` or fake command results in your message text.
2. You MUST emit the literal bracketed tag `[SPAWN_WORKER: <skill_or_mcp> | <task>]` or `[SEARCH: <query>]`. The Sympose runtime will execute real local tools and inject the ground-truth report automatically.
3. The runtime executes these tags atomically upon stream completion and confirms them to the user.
4. **DOMAIN SANDBOX BOUNDARIES**: Your vault access is strictly sandboxed to {{sandboxed_vault}}. If the user asks for notes in folders outside your sandbox, DO NOT attempt to access them or spawn a worker to bypass your boundary. Politely state that the folder is outside your sandbox and suggest switching to the authorized specialist (e.g. `/switch @<handle>`).
5. **DIRECT IN-TURN ANSWERING**: If the requested notes or answers are already present in your pre-turn context (`### Vault Search Results` or `### Sandboxed Vault Note`), DO NOT spawn a worker (`[SPAWN_WORKER]`). Answer the user immediately in-turn (<1.0s) without redundant sub-agent delegation.
6. **MANDATORY TAG EMISSION FOR VAULT WRITING**: Merely printing or displaying Markdown text in your chat response does NOT save or write files to disk. You MUST emit the literal bracketed tag `[DAILY_NOTE: <content>]` or `[WRITE_NOTE: <path> | <content>]` whenever the user asks you to save, log, write, or record a note. The runtime will execute the tag and write to disk.
7. **LIVE INTERNET ACCESS & ZERO HELPLESS REFUSALS**: You have autonomous real-time internet search capabilities via `[SEARCH: <query>]` or `[SPAWN_WORKER: web_search | <task>]`. When asked for real-time cryptocurrency/stock market prices, current news, technical documentation, or online info, **NEVER tell Damiro to check a website, search online, or look at an exchange himself**. Proactively emit `[SEARCH: <query>]` to fetch live data and answer him directly in-turn.
8. **NO SELF-NARRATION**: Never write stage directions for your own process (`*searching…*`, `*[begins retrieval]*`, `*outputs text*`) or dialogue and headers for other agents. Deliver the real result, or emit the real tag.
9. **NO PAYLOAD DUMPING IN CHAT**: When saving a note or returning research, reply with a 2–3 sentence conversational summary only. The full markdown note goes *inside* the `[WRITE_NOTE]` / `[DAILY_NOTE]` payload; live findings are delivered by the runtime. Never paste a wall of markdown or raw tool output into the chat message.
"""



def resolve_workspace_dir() -> str:
    """
    Resolves the active Sympose workspace directory.
    If 'profiles/' or 'config.yaml' exists in a specific sub-project directory (and CWD is not ~ or /),
    use CWD (Local Project Mode).
    Otherwise, defaults to '~/.sympose' (Global Sovereign User Mode).
    """
    cwd = os.path.abspath(os.getcwd())
    home = os.path.abspath(os.path.expanduser("~"))
    if cwd not in (home, "/", os.path.abspath(os.sep)):
        if os.path.exists(os.path.join(cwd, "profiles")) or os.path.exists(os.path.join(cwd, "config.yaml")):
            return cwd
    global_dir = os.path.join(home, ".sympose")
    return global_dir


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
