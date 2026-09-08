"""
Interactive Tab Auto-Completer and Command History for Sympose CLI.
"""

import os
import atexit
from typing import List, Optional, Any
from sympose.skills import skill_manager
from sympose.mcp import mcp_registry
from sympose.config import DEFAULT_CHAT_MODEL
from sympose.config_schema import global_settings as _global_settings, persona_settings as _persona_settings
from sympose.completer_rules import command_completions

try:
    import readline
except ImportError:
    readline = None


class SymposeCompleter:
    """Provides context-aware Tab completion and history navigation for Sympose."""

    ROOT_COMMANDS = [
        "/history",
        "/sessions",
        "/switch",
        "/setup",
        "/onboard",
        "/wizard",
        "/ask",
        "/model",
        "/render",
        "/config",
        "/commands",
        "/persona",
        "/vault",
        "/vaults",
        "/read",
        "/view",
        "/open",
        "/backlinks",
        "/note",
        "/daily",
        "/remember",
        "/compact",
        "/skill",
        "/skills",
        "/tools",
        "/worker",
        "/save",
        "/reset",
        "/new",
        "/clear",
        "/cls",
        "/delete",
        "/retire",
        "/help",
        "/exit",
        "exit",
        "quit",
    ]

    SAVE_OPTIONS = ["both", "memory", "obsidian"]

    COMMON_MODELS = [
        "list",
        "find",
        "refresh",
        "reset",
        "status",
        "openrouter/anthropic/claude-3.5-sonnet",
        "openrouter/deepseek/deepseek-r1",
        "openrouter/google/gemini-2.5-flash",
        "openrouter/meta-llama/llama-3.3-70b-instruct",
        DEFAULT_CHAT_MODEL,
        "anthropic/claude-3-5-sonnet-20241022",
        "openai/gpt-4o",
        "ollama/qwen2.5:7b",
    ]

    # Derived from the schema so /config set completion can never drift from it.
    CONFIG_KEYS = [s.key for s in _global_settings()]
    PERSONA_KEYS = [s.key for s in _persona_settings()]

    def __init__(self, engine: Any):
        self.engine = engine
        self.matches: List[str] = []

    def get_personas(self) -> List[str]:
        """Returns list of active persona handles formatted with @ prefix."""
        try:
            self.engine.pm.reload_profiles()
            return [f"@{h}" for h in self.engine.pm.profiles.keys()]
        except Exception:
            return [f"@{h}" for h in getattr(getattr(self.engine, "pm", None), "profiles", {}).keys()] or []

    def get_skills(self) -> List[str]:
        """Returns list of all available skill names."""
        try:
            skill_manager.reload_skills()
            return list(skill_manager.skills.keys())
        except Exception:
            return []

    def get_worker_targets(self) -> List[str]:
        """Returns combined list of procedural skills and MCP servers."""
        targets = []
        try:
            skill_manager.reload_skills()
            targets.extend(skill_manager.skills.keys())
        except Exception:
            pass
        try:
            targets.extend(mcp_registry.servers.keys())
        except Exception:
            pass
        return targets

    def get_session_ids(self) -> List[str]:
        """Returns list of recent session IDs."""
        try:
            from sympose.sessions import SessionManager
            sessions = SessionManager.list_sessions(limit=30)
            return [s["session_id"] for s in sessions]
        except Exception:
            return []

    def get_completions(self, line: str, text: str) -> List[str]:
        """Calculates completion candidates based on full line context and active word."""
        line_l = line.lstrip()

        # 1. Root Commands
        if not line_l or (line_l.startswith("/") and " " not in line_l):
            return [cmd for cmd in self.ROOT_COMMANDS if cmd.startswith(text)]

        # 2. Command sub-arguments & inline @mentions — routed per command.
        return command_completions(self, line_l, text)

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline callback returning candidate matching index state."""
        if state == 0:
            line = readline.get_line_buffer() if readline else text
            self.matches = self.get_completions(line, text)
        if state < len(self.matches):
            return self.matches[state]
        return None

    @classmethod
    def setup_readline(cls, engine: Any) -> Optional["SymposeCompleter"]:
        """Initializes readline bindings, completer, and persistent history."""
        if not readline:
            return None

        completer = cls(engine)
        readline.set_completer(completer.complete)
        # Custom delimiters preserving / and @ inside words
        readline.set_completer_delims(" \t\n`!#$%^&*()=+[{]}\\|;:'\",<>?")

        # Configure tab completion for macOS (libedit) and Linux (GNU readline)
        if "libedit" in (readline.__doc__ or ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

        # First Tab on an ambiguous prefix (or an empty line) lists every
        # candidate instead of beeping / silently completing the common prefix.
        for opt in ("set show-all-if-ambiguous on", "set show-all-if-unmodified on",
                    "set completion-ignore-case on"):
            try:
                readline.parse_and_bind(opt)
            except Exception:
                pass

        # Load history from active workspace directory
        from sympose.bootstrap import resolve_workspace_dir
        ws = resolve_workspace_dir()
        os.makedirs(ws, exist_ok=True)
        hist_path = os.path.join(ws, ".history")
        try:
            if os.path.exists(hist_path):
                readline.read_history_file(hist_path)
            readline.set_history_length(1000)
            atexit.register(readline.write_history_file, hist_path)
        except Exception:
            pass

        return completer
