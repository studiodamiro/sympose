"""
Interactive Tab Auto-Completer and Command History for Sympose CLI.
"""

import os
import atexit
from typing import List, Optional, Any
from sympose.skills import skill_manager
from sympose.mcp import mcp_registry
from sympose.models import ModelCatalog

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
        "/config",
        "/vault",
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
        "gemini/gemini-3.6-flash",
        "anthropic/claude-3-5-sonnet-20241022",
        "openai/gpt-4o",
        "ollama/qwen2.5:7b",
    ]

    CONFIG_KEYS = [
        "performance.request_timeout",
        "performance.local_request_timeout",
        "performance.max_context_turns",
        "performance.resume_context_turns",
        "performance.max_worker_tool_turns",
        "performance.stream",
        "session.exit_behavior.auto_save",
        "session.exit_behavior.default_target",
        "session.exit_behavior.clear_terminal",
        "session.exit_behavior.summarization_model",
        "memory.compaction_threshold",
        "memory.auto_compact",
        "runtime.default_persona",
        "vault.search_mode",
    ]

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

        # 2. Command Sub-Arguments
        tokens = line_l.split()
        cmd = tokens[0].lower()

        # /history, /sessions -> subcommands, session ids
        if cmd in ("/history", "/sessions"):
            history_subcmds = ["list", "all", "new", "resume", "view", "delete"]
            if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
                return [opt for opt in history_subcmds if opt.startswith(text)]
            sub = tokens[1].lower() if len(tokens) > 1 else ""
            if sub in ("resume", "load", "view", "show", "delete", "remove", "rm"):
                if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
                    s_ids = self.get_session_ids()
                    return [s for s in s_ids if s.startswith(text)]

        # /switch, /delete, /retire, /ask -> @persona handles
        if cmd in ("/switch", "/delete", "/retire", "/ask"):
            personas = self.get_personas()
            return [p for p in personas if p.startswith(text) or p.lstrip("@").startswith(text)]

        # /worker -> skills and mcp servers
        if cmd == "/worker":
            if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
                targets = self.get_worker_targets()
                return [t for t in targets if t.startswith(text)]

        # /skill, /skills, /tools -> subcommands, skill names, and @personas
        if cmd in ("/skill", "/skills", "/tools"):
            skill_subcmds = ["list", "add", "remove", "show"]
            all_skills = self.get_skills()

            # Subcommand completion: "/skill " or "/skill a"
            if len(tokens) == 1 or (len(tokens) == 2 and not line_l.endswith(" ")):
                options = skill_subcmds + all_skills
                return [opt for opt in options if opt.startswith(text)]

            sub = tokens[1].lower() if len(tokens) > 1 else ""

            # Skill name completion: "/skill add ", "/skill show ", "/skill remove "
            if sub in ("add", "mount", "install", "show", "view", "info", "remove", "unmount", "uninstall", "rm"):
                if len(tokens) == 2 or (len(tokens) == 3 and not line_l.endswith(" ")):
                    return [s for s in all_skills if s.startswith(text)]
                # Persona handle completion: "/skill add git_workflow @"
                if len(tokens) >= 3 and sub in ("add", "mount", "install", "remove", "unmount", "uninstall", "rm"):
                    return [p for p in self.get_personas() if p.startswith(text) or p.lstrip("@").startswith(text)]

        # /save -> both, memory, obsidian
        if cmd == "/save":
            return [opt for opt in self.SAVE_OPTIONS if opt.startswith(text)]

        # /config set -> config keys
        if cmd == "/config" and "set" in tokens:
            return [k for k in self.CONFIG_KEYS if k.startswith(text)]

        # /compact -> shared, @personas
        if cmd == "/compact":
            compact_targets = ["shared"] + self.get_personas()
            return [t for t in compact_targets if t.startswith(text) or t.lstrip("@").startswith(text)]

        # /model -> model presets, actions, and dynamic candidates
        if cmd == "/model":
            if len(tokens) >= 2 and tokens[1].lower() == "find":
                common_terms = ["sonnet", "deepseek", "flash", "qwen", "llama", "haiku", "opus", "gpt"]
                return [t for t in common_terms if t.startswith(text)]

            candidates = list(self.COMMON_MODELS)
            if text.startswith("openrouter/") or (len(tokens) >= 2 and tokens[1].startswith("openrouter/")):
                try:
                    dyn = ModelCatalog.get_completion_candidates(text)
                    for d in dyn:
                        if d not in candidates:
                            candidates.append(d)
                except Exception:
                    pass
            return [m for m in candidates if m.startswith(text)]

        # 3. Inline @mention completion
        if text.startswith("@"):
            return [p for p in self.get_personas() if p.startswith(text)]

        return []

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
