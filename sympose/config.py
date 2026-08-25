"""
Configuration, Security & Utility Helpers for Sympose.
"""

import os
import re
import logging
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

# Suppress verbose LiteLLM and external logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

# Load environment variables
load_dotenv()

# Prevent background Google Cloud GCE metadata server (169.254.169.254) and Vertex ADC timeouts on macOS
os.environ["NO_GCE_CHECK"] = "True"
os.environ["GOOGLE_CLOUD_DISABLE_METADATA"] = "true"
os.environ["GCE_METADATA_TIMEOUT"] = "0"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
os.environ.pop("VERTEXAI_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("GCP_PROJECT", None)

try:
    import litellm
    litellm.suppress_debug_info = True
    litellm.drop_params = True
    litellm.request_timeout = 10.0
except ImportError:
    litellm = None


class ConfigManager:
    """Manages master configuration loading, validation, and dynamic updates."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "performance": {
            "request_timeout": 10.0,
            "local_request_timeout": 60.0,
            "max_context_turns": 15,
            "max_worker_tool_turns": 8,
            "drop_unsupported_params": True,
            "stream": True,
        },
        "session": {
            "exit_behavior": {
                "auto_save": False,
                "default_target": "both",
                "clear_terminal": True,
                "obsidian_subfolder": "Sessions",
                "summarization_model": "gemini/gemini-3.5-flash-lite",
            }
        },
        "memory": {
            "user_profile_file": "profiles/user_profile.md",
            "shared_memory_file": "profiles/_shared_memory.md",
        },
        "runtime": {
            "default_persona": "samantha",
            "profiles_dir": "profiles",
        },
        "vault": {
            "daily_notes_folder": "Daily",
            "daily_notes_format": "Daily/%Y/%m-%B/%Y-%m-%d.md",
            "search_mode": "direct",
            "ignore_folders": [
                ".obsidian",
                ".git",
                "Attachments",
                "Drawings",
                "Movies",
                ".trash",
                "dot-files",
            ],
        },
    }

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> Dict[str, Any]:
        """Reloads configuration from YAML file and merges with defaults."""
        self.data = dict(self.DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        self._deep_merge(self.data, loaded)
            except Exception as e:
                logging.error(f"Error loading {self.config_path}: {e}")

        self._apply_runtime_settings()
        return self.data

    def _deep_merge(self, base: dict, override: dict) -> None:
        """Recursively merges override dictionary into base."""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _apply_runtime_settings(self) -> None:
        """Applies loaded performance knobs to third-party libraries like LiteLLM and loads MCP registry."""
        if litellm is not None:
            perf = self.data.get("performance", {})
            litellm.request_timeout = float(perf.get("request_timeout", 10.0))
            litellm.drop_params = bool(perf.get("drop_unsupported_params", True))

        try:
            from sympose.mcp import mcp_registry
            mcp_registry.load_from_config(self.data)
        except Exception:
            pass

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Gets a configuration value using dot notation (e.g. 'performance.request_timeout')."""
        keys = dotpath.split(".")
        val = self.data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, dotpath: str, value: Any) -> None:
        """Sets a configuration value using dot notation in memory."""
        keys = dotpath.split(".")
        d = self.data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self._apply_runtime_settings()

    def save(self) -> bool:
        """Persists current configuration to config.yaml on disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            logging.error(f"Failed to save {self.config_path}: {e}")
            return False


# Singleton default configuration manager
config_manager = ConfigManager()


def is_safe_path(target_path: str, base_dir: str = ".") -> bool:
    """Prevents directory traversal attacks (e.g. ../../etc/passwd)."""
    resolved_target = os.path.abspath(target_path)
    resolved_base = os.path.abspath(base_dir)
    return resolved_target.startswith(resolved_base)


def convert_md_to_slack_mrkdwn(text: str) -> str:
    """Converts standard LLM Markdown into Slack-compatible mrkdwn."""
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    text = re.sub(r"```[a-zA-Z]+\n", "```\n", text)
    return text
