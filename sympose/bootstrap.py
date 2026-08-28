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
except ImportError:
    Console = None


DEFAULT_CONFIG_YAML = """# Sympose Master Configuration
performance:
  request_timeout: 10.0
  max_context_turns: 15
  sub_second_streaming: true

runtime:
  default_persona: "samantha"
  profiles_dir: "profiles"

vault:
  daily_notes_folder: "Daily"
  daily_notes_format: "Daily/%Y/%m-%B/%Y-%m-%d.md"
  search_mode: "direct"
"""

SAMANTHA_YAML = """name: "Samantha"
handle: "samantha"
title: "Polymath Strategic Master Orchestrator"
aliases:
  - "sam"
model: "gemini/gemini-3.5-flash-lite"
icon_emoji: ":brain:"

vault_folders:
  - "General"
  - "Projects"
  - "Thoughts"
  - "Templates"

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
"""

DEFAULT_RULES_MD = """### Sovereign Workspace & Action Rules:
1. **Direct Markdown Memory**: Persist durable facts and decisions.
2. **Sub-Second Latency**: Deliver crisp, high-density analysis.
3. **Wikilink Synthesis**: Connect related ideas with [[Wikilinks]].
"""


def resolve_workspace_dir() -> str:
    """
    Resolves the active Sympose workspace directory.
    If 'profiles/' or 'config.yaml' exists in current working directory, use CWD (Local Project Mode).
    Otherwise, defaults to '~/.sympose' (Global Sovereign User Mode).
    """
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "profiles")) or os.path.exists(os.path.join(cwd, "config.yaml")):
        return cwd
    global_dir = os.path.expanduser("~/.sympose")
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

    os.makedirs(profiles_dir, exist_ok=True)
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(skills_dir, exist_ok=True)

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
    if not os.path.exists(rules_file):
        with open(rules_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_RULES_MD)

    return is_fresh


def run_first_run_onboarding(workspace_dir: str) -> None:
    """Interactive first-run wizard if no API keys are detected."""
    env_file = os.path.join(workspace_dir, ".env")
    
    # Check if any provider API key already exists in environment
    has_key = any(os.getenv(k) for k in ["OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"])
    if has_key or not sys.stdin.isatty():
        return

    console = Console() if Console else None
    if console:
        console.print(Panel.fit(
            "[bold cyan]🏛️  S Y M P O S E[/bold cyan]\n"
            "[dim]Zero-Bloat Multi-Model AI Agent Hub & Sovereign Vault Explorer[/dim]\n\n"
            f"[green]✨ Initialized sovereign workspace at[/green] [bold yellow]{workspace_dir}[/bold yellow]\n"
            "[magenta]Default Persona: @samantha (Polymath Strategic Orchestrator)[/magenta]",
            border_style="cyan"
        ))
        console.print("\n[bold yellow]🔑 Step 1 of 2: Connect your AI Provider[/bold yellow]")
        console.print("  [bold cyan][1][/bold cyan] Google Gemini [dim](Fast & Free tier available)[/dim]")
        console.print("  [bold cyan][2][/bold cyan] OpenRouter [dim](Access to Claude, Sonnet, Gemini, Qwen)[/dim]")
        console.print("  [bold cyan][3][/bold cyan] Anthropic Claude [dim](Direct API)[/dim]")
        console.print("  [bold cyan][4][/bold cyan] Skip for now [dim](Configure later in .env or local Ollama)[/dim]\n")
        
        choice = Prompt.ask("Select provider", choices=["1", "2", "3", "4"], default="1")
        key_var = {"1": "GEMINI_API_KEY", "2": "OPENROUTER_API_KEY", "3": "ANTHROPIC_API_KEY"}.get(choice)
        
        if key_var:
            api_key = Prompt.ask(f"Paste your {key_var.split('_')[0].title()} API Key", password=True).strip()
            if api_key:
                os.environ[key_var] = api_key
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{key_var}=\"{api_key}\"\n")
                console.print(f"[bold green]✅ Saved {key_var} to {env_file}[/bold green]\n")

        console.print("\n[bold yellow]📁 Step 2 of 2: Obsidian Vault Connection (Optional)[/bold yellow]")
        vault_path = Prompt.ask("Enter path to your Obsidian Vault / Notes folder [dim](press Enter to skip)[/dim]", default="").strip()
        if vault_path:
            os.environ["MASTER_VAULT_PATH"] = vault_path
            with open(env_file, "a", encoding="utf-8") as f:
                f.write(f"\nMASTER_VAULT_PATH=\"{vault_path}\"\n")
            console.print(f"[bold green]✅ Linked vault: {vault_path}[/bold green]\n")
        
        console.print("[bold green]🎉 Ready! Launching @samantha...[/bold green]\n")
