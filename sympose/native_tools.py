"""
Built-in Deterministic Execution Tools for Sympose Workers.
Provides safe local subprocess execution, file I/O, and tool schemas.
"""

import os
import re
import subprocess
from typing import Dict, Any, Tuple, Optional, List


class NativeTools:
    """Built-in deterministic tools available to all workers for local execution."""

    # ADR-073: default argv[0] allowlist for `run_command`. A worker task is
    # model-directed, unreviewed shell execution — a substring blocklist (the
    # previous guard) is trivially bypassed by rephrasing. Overridable via
    # `worker.shell_allowlist` in config.yaml; keep it read-only/inspection
    # commands unless you deliberately widen it.
    DEFAULT_SHELL_ALLOWLIST = [
        "ls", "cat", "grep", "egrep", "fgrep", "find", "git", "echo", "pwd",
        "head", "tail", "wc", "sort", "uniq", "cut", "tree", "date", "which",
        "env", "printf", "diff", "file", "stat", "du", "df", "basename",
        "dirname", "realpath",
    ]

    NATIVE_SCHEMAS = [
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Execute a shell command locally in the project workspace (e.g. git status, git diff, pytest, ls, find).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The exact shell command line to run.",
                        }
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the text contents of a file in the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative or absolute path to the file.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the live internet for articles, documentation, news, and technical questions ($0 / zero API key required).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search keywords or question.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Number of results (default 5).",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    ]

    @classmethod
    def _shell_allowlist(cls) -> List[str]:
        """Reads `worker.shell_allowlist` from config; falls back to the built-in
        read/inspect command set if unset or malformed."""
        try:
            from sympose.config import config_manager
            configured = config_manager.get("worker.shell_allowlist", None)
            if isinstance(configured, list) and configured:
                return [str(c).strip().lower() for c in configured if str(c).strip()]
        except Exception:
            pass
        return cls.DEFAULT_SHELL_ALLOWLIST

    @staticmethod
    def _segment_commands(cmd: str) -> List[str]:
        """Splits a shell command line on top-level `&& || ; |` operators (best-effort,
        ignoring operators inside quotes) and returns each segment's argv[0] lowercased."""
        segments = re.split(r'(?:&&|\|\||;|\|)(?=(?:[^"\']*(?:"[^"]*"|\'[^\']*\'))*[^"\']*$)', cmd)
        words = []
        for seg in segments:
            seg = seg.strip().lstrip("(").strip()
            if not seg:
                continue
            first = seg.split()[0] if seg.split() else ""
            first = first.strip("\"'")
            if first:
                words.append(first.lower())
        return words

    # ADR-073.2: environment vars a shelled-out worker command genuinely needs
    # to behave like a normal shell (PATH, locale, home dir, git identity) —
    # everything else, `*_API_KEY`/`*_TOKEN`/`AWS_*`/`SSH_*` credentials
    # included, is withheld regardless of an allowlisted command's own intent.
    _ENV_PASSTHROUGH_KEYS = {"PATH", "HOME", "LANG", "LC_ALL", "USER", "SHELL", "TERM", "TMPDIR", "PWD"}
    _ENV_PASSTHROUGH_PREFIXES = ("GIT_",)

    @classmethod
    def _scrubbed_env(cls) -> Dict[str, str]:
        """A minimal subprocess environment: no provider API keys, tokens, or
        cloud/SSH credentials leak into a model-directed shell command."""
        return {
            k: v for k, v in os.environ.items()
            if k in cls._ENV_PASSTHROUGH_KEYS or k.startswith(cls._ENV_PASSTHROUGH_PREFIXES)
        }

    @classmethod
    def execute(cls, tool_name: str, args: Dict[str, Any], allowed_dirs: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Executes a built-in native tool and returns (success, output)."""
        if tool_name == "run_command":
            cmd = args.get("command", "").strip()
            if not cmd:
                return False, "Error: No command provided."

            allowlist = cls._shell_allowlist()
            argv0s = cls._segment_commands(cmd)
            disallowed = sorted({w for w in argv0s if w not in allowlist})
            if disallowed:
                return False, (
                    f"Security Error: Command blocked by worker shell allowlist (ADR-073): "
                    f"`{', '.join(disallowed)}` not permitted. Add to `worker.shell_allowlist` "
                    f"in config.yaml to allow it."
                )

            if allowed_dirs:
                mv = os.getenv("MASTER_VAULT_PATH")
                if mv and os.path.exists(mv):
                    allowed_rel = {os.path.relpath(d, mv).lower() for d in allowed_dirs}
                    try:
                        all_subdirs = [d for d in os.listdir(mv) if os.path.isdir(os.path.join(mv, d)) and not d.startswith(".")]
                        for f_sub in [d for d in all_subdirs if d.lower() not in allowed_rel]:
                            if re.search(rf"(?:^|[/\\s\"']){re.escape(f_sub.lower())}(?:[/\\s\"'\.]|$)", cmd.lower()):
                                return False, f"Security Error: Command targets `{f_sub}/` which is outside assigned vault sandbox."
                    except Exception:
                        pass

            try:
                res = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    cwd=os.getcwd(),
                    env=cls._scrubbed_env(),
                )
                stdout = res.stdout.strip()
                stderr = res.stderr.strip()
                output = stdout
                if stderr:
                    output = (output + f"\n[stderr]:\n{stderr}").strip() if output else f"[stderr]:\n{stderr}"
                if not output:
                    output = "(Command executed successfully with no stdout output)"
                return (res.returncode == 0), output
            except subprocess.TimeoutExpired:
                return False, f"Command timed out after 20s: `{cmd}`"
            except Exception as e:
                return False, f"Error executing command: {e}"

        elif tool_name == "read_file":
            raw_path = args.get("path", "").strip()
            if not raw_path:
                return False, "File path is required."
            mv = os.getenv("MASTER_VAULT_PATH")
            target = raw_path
            if not os.path.exists(target) and mv:
                vault_candidate = os.path.join(mv, raw_path)
                if os.path.exists(vault_candidate):
                    target = vault_candidate
            if not os.path.exists(target):
                return False, f"File not found: `{raw_path}`"

            # Check sandbox boundary if allowed_dirs is enforced
            if allowed_dirs:
                from sympose.config import is_safe_path
                target_abs = os.path.abspath(target)
                is_in_workspace = is_safe_path(target_abs, os.getcwd())
                is_in_allowed_vault = any(is_safe_path(target_abs, d) for d in allowed_dirs)
                if not (is_in_workspace or is_in_allowed_vault):
                    return False, f"Security Error: Access to `{raw_path}` is outside assigned vault sandbox."

            try:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    return True, f.read()
            except Exception as e:
                return False, f"Error reading `{raw_path}`: {e}"

        elif tool_name == "web_search":
            query = args.get("query", "").strip()
            max_results = int(args.get("max_results", 5))
            if not query:
                return False, "Search query is required."
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                results = list(DDGS().text(query, max_results=max_results))
                if not results:
                    return True, "No search results found."
                formatted = [f"- **{r.get('title', 'Result')}**: {r.get('body', '')} (URL: {r.get('href', '')})" for r in results]
                return True, "\n".join(formatted)
            except Exception as e:
                return False, f"Web search error: {e}"

        return False, f"Unknown native tool: `{tool_name}`"
