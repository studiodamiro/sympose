"""
Built-in Deterministic Execution Tools for Sympose Workers.
Provides safe local subprocess execution, file I/O, and tool schemas.
"""

import os
import subprocess
from typing import Dict, Any, Tuple


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
    ]

    @classmethod
    def execute(cls, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """Executes a built-in native tool and returns (success, output)."""
        if tool_name == "run_command":
            cmd = args.get("command", "").strip()
            if not cmd:
                return False, "Error: No command provided."

            # Prevent catastrophic destructive commands
            forbidden = ["rm -rf /", "mkfs", ":(){ :|:& };:"]
            if any(f in cmd for f in forbidden):
                return False, f"Security Error: Command blocked by safety policy: {cmd}"

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
            path = args.get("path", "").strip()
            if not path or not os.path.exists(path):
                return False, f"File not found: `{path}`"
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return True, f.read()
            except Exception as e:
                return False, f"Error reading `{path}`: {e}"

        return False, f"Unknown native tool: `{tool_name}`"
