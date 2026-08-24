#!/usr/bin/env python3
"""
🏛️ Sympose: Zero-Bloat Multi-Model AI Agent Hub
Core Runtime Engine (CLI & Agent Manager)
"""

import os
import sys
import re
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import yaml
from dotenv import load_dotenv

# Suppress verbose LiteLLM and external logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

# Load environment variables from .env if present
load_dotenv()

try:
    import litellm
    litellm.suppress_debug_info = True
except ImportError:
    litellm = None

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None


# ==============================================================================
# 1. Security & Helper Utilities
# ==============================================================================

def is_safe_path(target_path: str, base_dir: str = ".") -> bool:
    """Prevents directory traversal attacks (e.g. ../../etc/passwd)."""
    resolved_target = os.path.abspath(target_path)
    resolved_base = os.path.abspath(base_dir)
    return resolved_target.startswith(resolved_base)


def convert_md_to_slack_mrkdwn(text: str) -> str:
    """Converts standard LLM Markdown into Slack-compatible mrkdwn."""
    # Convert headers (# Header) to bold (*Header*)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Convert bold (**bold**) to (*bold*)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    # Convert code blocks (```python -> ```)
    text = re.sub(r"```[a-zA-Z]+\n", "```\n", text)
    return text


# ==============================================================================
# 2. Dynamic Profile & Soul Manager
# ==============================================================================

class ProfileManager:
    """Dynamically loads and manages YAML agent profiles, souls, and memories."""

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.reload_profiles()

    def reload_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Scans profiles_dir and loads all valid *.yaml configurations."""
        self.profiles.clear()
        if not os.path.exists(self.profiles_dir):
            return self.profiles

        for filepath in glob.glob(os.path.join(self.profiles_dir, "*.yaml")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "handle" in data:
                        handle = data["handle"].lower()
                        self.profiles[handle] = data
            except Exception as e:
                print(f"⚠️ Error loading profile {filepath}: {e}", file=sys.stderr)

        return self.profiles

    def get_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        """Retrieves a loaded profile by handle."""
        return self.profiles.get(handle.lower())

    def list_personas(self) -> List[Dict[str, Any]]:
        """Returns a list of all active persona configurations."""
        return list(self.profiles.values())

    def build_system_prompt(self, profile: Dict[str, Any]) -> str:
        """Constructs the composite system prompt from soul, memory, and rules."""
        prompt_parts = []

        # 1. Soul directives
        soul_file = profile.get("soul_file")
        if soul_file and os.path.exists(soul_file):
            try:
                with open(soul_file, "r", encoding="utf-8") as f:
                    prompt_parts.append(f.read().strip())
            except Exception as e:
                prompt_parts.append(f"Soul Error: Unable to read {soul_file}: {e}")

        # 2. Persistent working memory
        memory_file = profile.get("memory_file")
        if memory_file and os.path.exists(memory_file):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    mem_content = f.read().strip()
                    if mem_content:
                        prompt_parts.append(f"### Persistent Working Memory:\n{mem_content}")
            except Exception as e:
                prompt_parts.append(f"Memory Error: Unable to read {memory_file}: {e}")

        # 3. Global workspace rules (if present)
        if os.path.exists("workspace_rules.md"):
            try:
                with open("workspace_rules.md", "r", encoding="utf-8") as f:
                    rules_content = f.read().strip()
                    if rules_content:
                        prompt_parts.append(f"### Global Workspace Rules:\n{rules_content}")
            except Exception:
                pass

        # 4. Context awareness of peer personas (for delegation)
        other_agents = [
            f"- @{p['handle']}: {p.get('name', p['handle'])} ({p.get('title', 'Specialist')})"
            for p in self.profiles.values()
            if p["handle"] != profile["handle"]
        ]
        if other_agents:
            prompt_parts.append("### Available Specialist Peers in Sympose:\n" + "\n".join(other_agents))

        return "\n\n".join(prompt_parts)

    def append_memory(self, handle: str, fact: str) -> bool:
        """Appends a new fact to the persona's _memory.md file."""
        profile = self.get_profile(handle)
        if not profile:
            return False

        memory_file = profile.get("memory_file")
        if not memory_file:
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(memory_file)), exist_ok=True)
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(f"\n- {fact.strip()}")
            return True
        except Exception as e:
            print(f"⚠️ Failed to write memory to {memory_file}: {e}", file=sys.stderr)
            return False


# ==============================================================================
# 3. Sandboxed Vault Searcher (ADR-002 & ADR-003)
# ==============================================================================

class VaultSearcher:
    """Performs sandboxed search inside the persona's allowed domain directory."""

    @staticmethod
    def search(profile: Dict[str, Any], query: str) -> str:
        master_vault = os.getenv("MASTER_VAULT_PATH")
        if not master_vault or not os.path.exists(master_vault):
            return "⚠️ Master notes directory (`MASTER_VAULT_PATH`) is not configured or does not exist."

        vault_folder = profile.get("vault_folder", "")
        allowed_dir = os.path.join(master_vault, vault_folder) if vault_folder else master_vault

        if not os.path.exists(allowed_dir):
            return f"⚠️ Assigned folder `{vault_folder}` does not exist in master vault."

        # Security check: sandboxing boundary
        if not is_safe_path(allowed_dir, master_vault):
            return "⚠️ Security violation: Target directory is outside sandbox root."

        query_lower = query.lower()
        matches = []

        try:
            for root, _, files in os.walk(allowed_dir):
                for file in files:
                    if file.endswith(".md"):
                        file_path = os.path.join(root, file)
                        # Check filename or content match
                        if query_lower in file.lower():
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                excerpt = f.read(1500).strip()
                                matches.append(f"📄 **{file}** (Title match):\n{excerpt}")
                                if len(matches) >= 2:
                                    break
                        else:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in content.lower():
                                    snippet = content[:1200].strip()
                                    matches.append(f"📄 **{file}** (Content match):\n{snippet}")
                                    if len(matches) >= 2:
                                        break
                if len(matches) >= 2:
                    break
        except Exception as e:
            return f"⚠️ Error searching vault: {e}"

        if not matches:
            return f"No notes found matching `{query}` in `{vault_folder}/`."

        return "\n\n---\n\n".join(matches)


# ==============================================================================
# 4. Multi-Model Persona Engine
# ==============================================================================

class PersonaEngine:
    """Executes multi-model AI completions with sliding context and command interceptors."""

    def __init__(self, profile_manager: ProfileManager, max_turns: int = 15):
        self.pm = profile_manager
        self.max_turns = max_turns
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.model_overrides: Dict[str, str] = {}

    def get_history(self, handle: str) -> List[Dict[str, str]]:
        return self.histories.setdefault(handle.lower(), [])

    def reset_history(self, handle: str) -> None:
        self.histories[handle.lower()] = []

    def chat_stream(self, handle: str, user_message: str):
        """Streams AI responses token-by-token or yields instant command replies."""
        profile = self.pm.get_profile(handle)
        if not profile:
            yield f"⚠️ Persona `@{handle}` not found."
            return

        clean_input = user_message.strip()

        # Intercept tactical slash commands
        if clean_input in ("/reset", "/new"):
            self.reset_history(handle)
            yield f"🔄 Reset conversation history for **{profile.get('name', handle)}**. Context refreshed."
            return

        if clean_input.startswith("/remember "):
            fact = clean_input[10:].strip()
            if not fact:
                yield "⚠️ Usage: `/remember <fact to save>`"
                return
            success = self.pm.append_memory(handle, fact)
            if success:
                yield f"🧠 **Saved to {profile.get('name', handle)}'s memory:**\n> {fact}"
            else:
                yield f"⚠️ Failed to save memory to {profile.get('name', handle)}."
            return

        if clean_input.startswith("/model "):
            new_model = clean_input[7:].strip()
            if not new_model:
                yield "⚠️ Usage: `/model <provider/model_name>`"
                return
            self.model_overrides[handle.lower()] = new_model
            yield f"🎛️ Model for **{profile.get('name', handle)}** temporarily set to `{new_model}` for this session."
            return

        if clean_input.startswith("/vault "):
            query = clean_input[7:].strip()
            if not query:
                yield "⚠️ Usage: `/vault <search query>`"
                return
            yield VaultSearcher.search(profile, query)
            return

        if clean_input == "/help":
            yield (
                "**Available Slash Commands:**\n"
                "- `/remember <fact>`: Save fact into persona's persistent `_memory.md`\n"
                "- `/reset` or `/new`: Clear active conversation context\n"
                "- `/model <name>`: Temporarily switch backend model\n"
                "- `/vault <query>`: Query persona's sandboxed notes\n"
                "- `/help`: Show this command list"
            )
            return

        # Build dynamic system prompt
        system_prompt = self.pm.build_system_prompt(profile)
        history = self.get_history(handle)

        active_messages = [{"role": "system", "content": system_prompt}]
        active_messages.extend(history[-(self.max_turns * 2):])
        active_messages.append({"role": "user", "content": user_message})

        target_model = self.model_overrides.get(handle.lower(), profile.get("model", "gemini/gemini-3.6-flash"))
        api_base = profile.get("api_base")

        if litellm is None:
            yield "⚠️ LiteLLM is not installed. Please run `pip install -r requirements.txt`."
            return

        try:
            kwargs = {
                "model": target_model,
                "messages": active_messages,
                "stream": True,
            }
            if "temperature" in profile:
                kwargs["temperature"] = profile["temperature"]
            if api_base:
                kwargs["api_base"] = api_base

            response = litellm.completion(**kwargs)
            full_reply = []

            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_reply.append(delta)
                    yield delta

            complete_text = "".join(full_reply)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": complete_text})
            self.histories[handle.lower()] = history[-(self.max_turns * 2):]

        except Exception as e:
            err_str = str(e)
            if "11434" in err_str or "Connection refused" in err_str:
                yield (
                    f"⚠️ **Local Model Offline ({target_model})**\n\n"
                    f"Marcus Aurelius runs locally on your Mac. Please start the Ollama daemon by running:\n"
                    f"```bash\nollama serve\n```"
                )
            elif "API key" in err_str or "AuthenticationError" in err_str:
                yield f"⚠️ **Authentication Error:** Missing or invalid API key for model `{target_model}`. Check `.env`."
            else:
                yield f"⚠️ **Runtime Error ({target_model}):** {err_str}"


# ==============================================================================
# 5. Interactive Terminal CLI Interface
# ==============================================================================

class TerminalInterface:
    """Rich interactive Terminal UI for Sympose with smooth real-time streaming."""

    def __init__(self, engine: PersonaEngine):
        self.engine = engine
        self.pm = engine.pm
        self.console = Console() if Console else None

    def display_banner(self) -> None:
        if not self.console:
            print("=== Sympose AI Agent Hub ===")
            return

        banner_text = Text()
        banner_text.append("🏛️ SYMPOSE: Multi-Model Agent Hub\n", style="bold cyan")
        banner_text.append("Zero-bloat orchestrator for macOS & Slack\n", style="dim white")
        banner_text.append("Type /help for commands, /switch to change persona, or 'exit' to quit.", style="italic green")

        self.console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))

    def select_persona(self, default_handle: str = "samantha") -> str:
        profiles = self.pm.list_personas()
        if not profiles:
            if self.console:
                self.console.print("[bold red]⚠️ No profiles found in profiles/ directory![/bold red]")
            return default_handle

        if not self.console:
            return default_handle

        table = Table(title="Available Personas", border_style="dim cyan", show_header=True)
        table.add_column("Handle", style="bold yellow")
        table.add_column("Name", style="bold white")
        table.add_column("Domain / Title", style="cyan")
        table.add_column("Default Model", style="green")
        table.add_column("Sandbox", style="magenta")

        for p in profiles:
            table.add_row(
                f"@{p.get('handle')}",
                p.get("name", ""),
                p.get("title", ""),
                p.get("model", ""),
                f"{p.get('vault_folder', 'None')}/"
            )

        self.console.print(table)
        choice = Prompt.ask("\nSelect persona handle", default=default_handle, choices=[p["handle"] for p in profiles])
        return choice.lower()

    def run(self, initial_handle: str = "samantha") -> None:
        self.display_banner()
        current_handle = initial_handle

        if current_handle not in self.pm.profiles:
            current_handle = self.select_persona(default_handle="samantha")

        while True:
            profile = self.pm.get_profile(current_handle)
            name = profile.get("name", current_handle) if profile else current_handle
            model = self.engine.model_overrides.get(current_handle, profile.get("model", "")) if profile else ""

            prompt_label = f"\n[bold yellow]You[/bold yellow] (to [bold cyan]@{current_handle}[/bold cyan] | [dim]{model}[/dim])"

            try:
                if self.console:
                    user_input = Prompt.ask(prompt_label).strip()
                else:
                    user_input = input(f"\nYou (to @{current_handle}): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting Sympose.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", ":q"):
                if self.console:
                    self.console.print("[dim cyan]Goodbye.[/dim cyan]")
                break

            if user_input.startswith("/switch"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].replace("@", "") in self.pm.profiles:
                    current_handle = parts[1].replace("@", "").lower()
                    if self.console:
                        self.console.print(f"[bold green]Switched to @{current_handle}[/bold green]")
                else:
                    current_handle = self.select_persona(default_handle=current_handle)
                continue

            # Stream response in real-time
            if self.console:
                self.console.print(f"\n[bold cyan]🏛️ {name}:[/bold cyan]")
            else:
                print(f"\n🏛️ {name}:")

            for chunk in self.engine.chat_stream(current_handle, user_input):
                sys.stdout.write(chunk)
                sys.stdout.flush()

            print("\n")


# ==============================================================================
# 6. Main Entry Point
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sympose Multi-Model Agent Hub")
    parser.add_argument("--cli", action="store_true", help="Launch interactive Terminal CLI Hub")
    parser.add_argument("--persona", type=str, default="samantha", help="Initial persona handle (samantha, grace, aurelius)")
    parser.add_argument("--slack", action="store_true", help="Launch Slack Socket Mode Daemon")
    args = parser.parse_args()

    pm = ProfileManager()
    engine = PersonaEngine(pm)

    if args.slack:
        print("⚡ Starting Slack Socket Mode Daemon...")
        # Will be connected in Phase 2
        print("⚠️ Slack Daemon module will initialize once Slack app tokens are configured in .env.")
        sys.exit(0)
    else:
        cli = TerminalInterface(engine)
        cli.run(initial_handle=args.persona)


if __name__ == "__main__":
    main()
