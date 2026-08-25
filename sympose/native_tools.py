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
    def execute(cls, tool_name: str, args: Dict[str, Any], allowed_dirs: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Executes a built-in native tool and returns (success, output)."""
        if tool_name == "run_command":
            cmd = args.get("command", "").strip()
            if not cmd:
                return False, "Error: No command provided."

            forbidden = ["rm -rf /", "mkfs", ":(){ :|:& };:"]
            if any(f in cmd for f in forbidden):
                return False, f"Security Error: Command blocked by safety policy: {cmd}"

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
                from ddgs import DDGS
                results = list(DDGS().text(query, max_results=max_results))
                if not results:
                    return True, "No search results found."
                formatted = [f"- **{r.get('title', 'Result')}**: {r.get('body', '')} (URL: {r.get('href', '')})" for r in results]
                return True, "\n".join(formatted)
            except Exception as e:
                return False, f"Web search error: {e}"

        return False, f"Unknown native tool: `{tool_name}`"
