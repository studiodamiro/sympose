"""
Bootstrap, Workspace Resolver & First-Run Onboarding for Sympose.
"""

import difflib
import logging
import os
import sys

import yaml

log = logging.getLogger(__name__)

try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
except ImportError:
    Console = None
    ROUNDED = None

from sympose.config import DEFAULT_CHAT_MODEL
from sympose.config_schema import build_default_config
from sympose.prompt_assets import load_prompt
from sympose.workspace import (
    resolve_workspace_dir,  # noqa: F401  (re-exported for existing callers)
)

_CONFIG_SEED_HEADER = (
    "# Sympose Master Configuration\n"
    "# Generated from the schema in sympose/config_schema.py — every global default.\n"
    "# Key reference (types, allowed values, live-vs-restart):\n"
    "#   docs/wiki/reference/configuration.md\n"
    "# Edit any value freely; unknown keys are ignored. `/config set` rewrites this "
    "file at runtime.\n\n"
)


def render_seed_config() -> str:
    """Starter `config.yaml` for a fresh workspace: the schema's global defaults
    serialised in full, with no hand-maintained key list left to drift."""
    return _CONFIG_SEED_HEADER + yaml.safe_dump(
        build_default_config(), sort_keys=False, default_flow_style=False
    )


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
  - "vault_read"
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
- **Sympose Mastery & Autonomous Actions**: You have full mastery of the Sympose runtime environment (`sympose_mastery`). When requested, autonomously emit `[CREATE_PERSONA: <handle> | <yaml>]`, `[CONFIG_SET: <key> | <value>]`, `[REMEMBER: <fact>]`, and `[WRITE_NOTE: <file> | <content>]`. Never simulate creating a persona in roleplay; always emit `[CREATE_PERSONA]` directly.
"""

# The full ruleset is the packaged file sympose/prompts/workspace_rules.md
# (shipped via package-data). This inline string is only a last-resort seed for
# a corrupt install where that file cannot be read; keep it minimal — do not
# re-grow it into a second copy of the ruleset.
_RULES_MD_FALLBACK = """# 🏛️ Sympose: Universal Workspace & Action Rules

### Runtime Environment
- App Workspace Root: `{{workspace_root}}`
- Master Obsidian Vault: `{{master_vault_path}}`
- Sandboxed Vault Access: {{sandboxed_vault}}
- Memory Mode: {{memory_mode}}
- Current Date & Time: {{current_datetime}}

### Directives
1. Never fabricate. Your only knowledge of user history is {{sources}} plus the active turns; if a fact isn't there, say so.
2. No time-delay simulation — deliver findings in the current turn.
3. Actions happen only by emitting the runtime tag (`[REMEMBER]`, `[READ_NOTE]`, `[WRITE_NOTE]`, `[DAILY_NOTE]`, `[SEARCH]`, `[SPAWN_SUB_AGENT]`, `[CONFIG_SET]`, `[CREATE_PERSONA]`, `[DELETE_PERSONA]`) — describing or roleplaying the action does nothing.
4. Stay in your sandbox ({{sandboxed_vault}}); point out-of-scope requests to the right specialist.
5. No self-narration, no faked sub-agent reports, no payload dumping — summarize in 2–3 sentences and let the runtime inject ground truth.
"""

# Full ruleset from the packaged file; the minimal fallback only applies to a
# corrupt install. Consumers (bootstrap seeding, profiles.build_system_prompt)
# still substitute the {{...}} placeholders at use time.
DEFAULT_RULES_MD = load_prompt("workspace_rules.md", _RULES_MD_FALLBACK)


def _seed_config(workspace_dir: str) -> bool:
    """Seeds config.yaml. Returns True if it didn't already exist."""
    config_file = os.path.join(workspace_dir, "config.yaml")
    if os.path.exists(config_file):
        return False
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(render_seed_config())
    return True


def _seed_samantha_profile(profiles_dir: str) -> bool:
    """Seeds the starter Samantha profile. Returns True if samantha.yaml
    didn't already exist (the soul file alone doesn't count as "fresh")."""
    is_fresh = False
    sam_yaml_file = os.path.join(profiles_dir, "samantha.yaml")
    if not os.path.exists(sam_yaml_file):
        is_fresh = True
        with open(sam_yaml_file, "w", encoding="utf-8") as f:
            f.write(SAMANTHA_YAML)

    sam_soul_file = os.path.join(profiles_dir, "samantha_soul.md")
    if not os.path.exists(sam_soul_file):
        with open(sam_soul_file, "w", encoding="utf-8") as f:
            f.write(SAMANTHA_SOUL_MD)
    return is_fresh


def _seed_user_and_shared_memory(profiles_dir: str) -> None:
    user_card = os.path.join(profiles_dir, "user_profile.md")
    if not os.path.exists(user_card):
        with open(user_card, "w", encoding="utf-8") as f:
            f.write(
                f"# Universal User Profile\n\n- **Primary User**: {os.getenv('USER', 'User')}\n- **Environment**: {sys.platform}\n"
            )

    shared_mem = os.path.join(profiles_dir, "_shared_memory.md")
    if not os.path.exists(shared_mem):
        with open(shared_mem, "w", encoding="utf-8") as f:
            f.write(
                "# Shared Team Working Memory\n\n- **Active Workspace**: Initialized\n"
            )


def _seed_workspace_rules(prompts_dir: str) -> None:
    rules_file = os.path.join(prompts_dir, "workspace_rules.md")
    if not os.path.exists(rules_file) or os.path.getsize(rules_file) < 300:
        with open(rules_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_RULES_MD)


def _seed_default_skills(skills_dir: str) -> None:
    try:
        import shutil

        default_skills_dir = os.path.join(os.path.dirname(__file__), "default_skills")
        if not os.path.exists(default_skills_dir):
            return
        for item in os.listdir(default_skills_dir):
            s_src = os.path.join(default_skills_dir, item)
            s_dst = os.path.join(skills_dir, item)
            if os.path.exists(s_dst):
                continue
            if os.path.isdir(s_src):
                shutil.copytree(s_src, s_dst)
            elif os.path.isfile(s_src) and s_src.endswith(".md"):
                shutil.copy2(s_src, s_dst)
    except Exception as e:
        log.warning("Failed to seed default skills into %s: %s", skills_dir, e)


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

    is_fresh = _seed_config(workspace_dir)
    is_fresh = _seed_samantha_profile(profiles_dir) or is_fresh
    _seed_user_and_shared_memory(profiles_dir)
    _seed_workspace_rules(prompts_dir)
    _seed_default_skills(skills_dir)

    return is_fresh


def sync_default_content(workspace_dir: str, auto_yes: bool = False) -> list[str]:
    """Brings an existing workspace's copies of the packaged prompt/skill
    files up to date with what's currently installed. `ensure_workspace`
    above only ever seeds these once and never overwrites an existing file —
    by design, so a hand-edited workspace_rules.md or SKILL.md survives a
    reinstall — but that also means a packaged fix or rewrite (a rename, a
    corrected tag, a rephrased playbook) never reaches an existing workspace
    on its own, no matter how many times the package is upgraded. Run via
    `sympose --sync-skills` after an upgrade. Prompts before overwriting
    anything that differs, since the difference could be a real edit rather
    than staleness; pass auto_yes to overwrite without asking."""
    prompts_dir = os.path.join(workspace_dir, "prompts")
    skills_dir = os.path.join(workspace_dir, "skills")
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(skills_dir, exist_ok=True)

    candidates: list[tuple[str, str]] = [
        (os.path.join(prompts_dir, "workspace_rules.md"), DEFAULT_RULES_MD)
    ]
    default_skills_dir = os.path.join(os.path.dirname(__file__), "default_skills")
    if os.path.exists(default_skills_dir):
        for item in sorted(os.listdir(default_skills_dir)):
            src = os.path.join(default_skills_dir, item, "SKILL.md")
            if os.path.isfile(src):
                with open(src, "r", encoding="utf-8") as f:
                    candidates.append(
                        (os.path.join(skills_dir, item, "SKILL.md"), f.read())
                    )

    report: list[str] = []
    for dst, packaged_text in candidates:
        rel = os.path.relpath(dst, workspace_dir)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(packaged_text)
            report.append(f"seeded:     {rel}")
            continue

        with open(dst, "r", encoding="utf-8") as f:
            current_text = f.read()
        if current_text.strip() == packaged_text.strip():
            continue

        if not auto_yes:
            diff = "".join(
                difflib.unified_diff(
                    current_text.splitlines(keepends=True),
                    packaged_text.splitlines(keepends=True),
                    fromfile=f"{rel} (yours)",
                    tofile=f"{rel} (packaged)",
                    n=1,
                )
            )
            print(f"\n--- {rel} differs from the packaged version ---")
            print(diff[:2000])
            ans = input("Overwrite with the packaged version? [y/N] ").strip().lower()
            if ans != "y":
                report.append(f"kept local: {rel}")
                continue

        with open(dst, "w", encoding="utf-8") as f:
            f.write(packaged_text)
        report.append(f"updated:    {rel}")

    return report


def _offer_local_model_followup(console: "Console", workspace_dir: str) -> None:
    """Step 1 follow-up, only reached once a cloud provider was actually
    configured this run - ADR-122's own `local_model` setting is
    "meaningless" for a persona whose main model is already local (the
    out-of-box default), so there's nothing to offer if the user just
    skipped cloud setup entirely.

    Offers Samantha's free, near-instant local fallback for genuinely
    trivial messages (ADR-122) using whatever's actually pulled in Ollama
    already - `get_local_ollama_models()` queries the real local install,
    so this never asks the user to blind-type a model tag, and silently
    does nothing if Ollama isn't running or nothing's pulled yet."""
    from sympose.models import get_local_ollama_models

    local_models = get_local_ollama_models()
    if not local_models:
        return
    console.print(
        "\n[dim]A local Ollama model can also handle trivial messages "
        "(greetings, quick math) for free, instantly - anything with real "
        "weight still goes to the model above.[/dim]"
    )
    options = "\n".join(f"  {i + 1}. {m}" for i, m in enumerate(local_models))
    raw = Prompt.ask(
        f"Use one as Samantha's local fallback?\n{options}\n"
        f"[dim][1-{len(local_models)}, Enter to skip][/dim]",
        default="",
        show_default=False,
    ).strip()
    if not raw:
        return
    try:
        picked = local_models[int(raw) - 1]
    except (ValueError, IndexError):
        console.print(f"[yellow]⚠️ `{raw}` isn't one of the listed options - skipped.[/yellow]")
        return

    from sympose.profiles import ProfileManager

    pm = ProfileManager(os.path.join(workspace_dir, "profiles"))
    ok, msg = pm.set_persona_field("samantha", "local_model", f"ollama/{picked}")
    style = "green" if ok else "yellow"
    console.print(f"[{style}]{'✓' if ok else '⚠️'} {msg}[/{style}]")


def run_first_run_onboarding(workspace_dir: str, force: bool = False) -> None:
    """Interactive setup & onboarding wizard (runs on first launch or via sympose --setup)."""
    env_file = os.path.join(workspace_dir, ".env")

    # Check if any provider API key already exists in environment
    has_key = any(
        os.getenv(k)
        for k in [
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
        ]
    )
    if not force and (has_key or not sys.stdin.isatty()):
        return

    console = Console() if Console else None
    if console:
        from sympose.ui import TerminalUI

        TerminalUI.display_setup_banner(console, workspace_dir)

        # Display existing keys if any
        if force:
            existing = []
            for k in [
                "GEMINI_API_KEY",
                "OPENROUTER_API_KEY",
                "ANTHROPIC_API_KEY",
                "OPENAI_API_KEY",
                "MASTER_VAULT_PATH",
            ]:
                if val := os.getenv(k):
                    masked = val[:6] + "..." + val[-4:] if len(val) > 12 else "********"
                    existing.append(f"  • [bold]{k}[/bold]: [green]{masked}[/green]")
            if existing:
                console.print(
                    "\n[dim]Current Environment Variables:[/dim]\n"
                    + "\n".join(existing)
                )

        # Step 1: AI Provider Selection Panel
        provider_options = [
            "Google Gemini  [dim](Sub-second latency & free tier available — recommended)[/dim]",
            "OpenRouter     [dim](Unified access to Claude 3.5, Sonnet, DeepSeek, Qwen)[/dim]",
            "Anthropic      [dim](Direct Claude 3.5 Sonnet API key)[/dim]",
            "Skip / Custom  [dim](Keep current .env or local Ollama execution)[/dim]",
        ]
        TerminalUI.render_option_panel(
            console,
            title="🔑  STEP 1/2: CONNECT YOUR AI PROVIDER",
            options=provider_options,
        )

        prompt_label = (
            "\n[bold cyan]Select provider[/bold cyan] [dim][1-4, Enter for [1]][/dim]"
        )
        choice = Prompt.ask(
            prompt_label, default="1", show_choices=False, show_default=False
        ).strip()
        provider_map = {
            "1": ("GEMINI_API_KEY", DEFAULT_CHAT_MODEL),
            "2": ("OPENROUTER_API_KEY", "openrouter/google/gemini-2.5-flash"),
            "3": ("ANTHROPIC_API_KEY", "anthropic/claude-3-5-sonnet-20241022"),
        }

        if choice in provider_map:
            key_var, default_m = provider_map[choice]
            api_key = Prompt.ask(
                f"Paste your {key_var.split('_')[0].title()} API Key", password=True
            ).strip()
            if api_key:
                os.environ[key_var] = api_key
                os.environ["DEFAULT_MODEL"] = default_m
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f'\n{key_var}="{api_key}"\nDEFAULT_MODEL="{default_m}"\n')
                console.print(
                    f"\n[bold green]✓ Saved {key_var} and default model `{default_m}` to {env_file}[/bold green]"
                )
                _offer_local_model_followup(console, workspace_dir)

        # Step 2: Obsidian Vault Selection Panel
        vault_panel_text = (
            "Link your existing Obsidian / Markdown notes directory to enable `/vault` searching & synthesis.\n"
            "[dim]Press Enter without typing to keep standalone sandboxed storage.[/dim]"
        )
        console.print()
        console.print(
            Panel(
                vault_panel_text,
                box=ROUNDED,
                title="📁  STEP 2/2: OBSIDIAN VAULT CONNECTION (OPTIONAL)",
                title_align="left",
                border_style="cyan",
                padding=(0, 2),
            )
        )

        current_vault = os.getenv("MASTER_VAULT_PATH", "")
        vault_prompt = "Enter path to Obsidian Vault / Notes folder"
        vault_path = Prompt.ask(vault_prompt, default=current_vault).strip()
        if vault_path:
            os.environ["MASTER_VAULT_PATH"] = vault_path
            with open(env_file, "a", encoding="utf-8") as f:
                f.write(f'\nMASTER_VAULT_PATH="{vault_path}"\n')
            console.print(f"\n[bold green]✓ Linked vault: {vault_path}[/bold green]")

        # Persona Genesis nudge — Samantha is the only persona that ships.
        # Without this, a first-run user has no in-app signal that spawning
        # their own companion is a thing, let alone how. Deliberately NOT a
        # numbered "STEP" box like the two above: those both prompt for
        # real input, so the same boxed treatment here read as if a third
        # answer was expected — this is pure FYI, folded into the closing
        # message instead so the boxed/numbered format stays reserved for
        # things that actually ask you something.
        console.print(
            "\n[bold]🧬 @samantha[/bold] is your only persona out of the box. Want a "
            "companion for something specific — engineering, journaling, a domain "
            "specialist? Just ask her, in plain language, once you're chatting:\n"
            '  [cyan]"Create a persona modeled after Grace Hopper for surgical code reviews."[/cyan]\n'
            "She writes the new persona to disk and switches you to it immediately — "
            "no YAML required. `/switch @samantha` to come back anytime.\n"
        )

        console.print(
            "\n[bold green]🎉 Setup completed! Launching @samantha...[/bold green]\n"
        )
