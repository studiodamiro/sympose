"""
Configuration, Security & Utility Helpers for Sympose.
"""

import os
import re
import logging
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

from sympose.workspace import resolve_workspace_dir
from sympose.config_schema import build_default_config, default_for

# Suppress verbose LiteLLM and external logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

# Load the *workspace* .env only. A bare load_dotenv() walks up from this file's
# location and, in a repo / editable install, loads the repo's own .env first —
# and python-dotenv never overrides an already-set var, so the repo .env would
# then shadow the active workspace .env for every overlapping key. Scoping the
# load to resolve_workspace_dir() (a stdlib-only leaf module) makes this the one
# and only .env that is read, at import time, before DEFAULT_MODEL is resolved.
load_dotenv(os.path.join(resolve_workspace_dir(), ".env"))

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
    litellm.request_timeout = 30.0
except ImportError:
    litellm = None


# ---------------------------------------------------------------------------
# Canonical model fallback constants — change here to update everywhere
# ---------------------------------------------------------------------------
DEFAULT_CHAT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini/gemini-3.6-flash")
DEFAULT_WORKER_MODEL: str = os.getenv("DEFAULT_WORKER_MODEL", DEFAULT_CHAT_MODEL)


class ConfigManager:
    """Manages master configuration loading, validation, and dynamic updates.

    Runtime defaults are not held here — `config_schema.build_default_config()`
    materialises them from the one declarative `SETTINGS` list, and `config.yaml`
    is layered on top."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> Dict[str, Any]:
        """Reloads configuration from YAML file and merges it over the schema
        defaults. `build_default_config()` returns a fresh, independently-owned
        dict each call, so `set()` / `_deep_merge()` cannot corrupt anything
        shared."""
        self.data = build_default_config()
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
        """Gets a configuration value using dot notation (e.g. 'performance.request_timeout').

        Every global setting with a non-None schema default is materialised into
        `self.data` at load time, so a known key always resolves to its
        `config.yaml` value or that schema default. The `default` argument is
        only consulted for keys that are genuinely absent — unknown keys, or
        schema keys whose declared default is None (e.g. `local_keep_alive`) —
        and otherwise `config_schema`'s declared default is used."""
        keys = dotpath.split(".")
        val = self.data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default if default is not None else default_for(dotpath)
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
    """Prevents directory traversal attacks (e.g. ../../etc/passwd), sibling directory
    bypasses, and symlink escapes (resolves symlinks before comparing)."""
    try:
        resolved_target = os.path.realpath(target_path)
        resolved_base = os.path.realpath(base_dir)
        return os.path.commonpath([resolved_target, resolved_base]) == resolved_base
    except Exception:
        return False


def convert_md_to_slack_mrkdwn(text: str) -> str:
    """Converts standard LLM Markdown into Slack-compatible mrkdwn."""
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    text = re.sub(r"```[a-zA-Z]+\n", "```\n", text)
    # Strip backticks around #channel names so Slack renders native clickable channel links
    text = re.sub(r"`(#[\w\-]+)`", r"\1", text)
    # Strip backticks around @mentions
    text = re.sub(r"`(@[\w\-]+)`", r"\1", text)
    return text
