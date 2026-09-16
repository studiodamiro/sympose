"""
Configuration, Security & Utility Helpers for Sympose.
"""

import logging
import os
import re
from typing import Any

import yaml
from dotenv import load_dotenv

from sympose.config_schema import build_default_config, default_for
from sympose.workspace import resolve_workspace_dir

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
DEFAULT_SUB_AGENT_MODEL: str = os.getenv("DEFAULT_SUB_AGENT_MODEL", DEFAULT_CHAT_MODEL)

# Local inference backends, by litellm provider prefix. Shared by every call
# site that needs to know whether a model is local or cloud (grounding mode,
# request-timeout selection, ...) so the list itself is declared exactly once.
_LOCAL_MODEL_PREFIXES = (
    "ollama",
    "ollama_chat",
    "ollama_completion",
    "lm_studio",
    "llamafile",
    "llama-cpp-python",
)


def is_local_backend(model: str, api_base: str = "") -> bool:
    """True when `model`'s litellm provider prefix (or a localhost-looking
    `api_base`) points at a local inference backend rather than a cloud API.
    Both the main chat path and a spawned sub-agent's own call need this to
    pick the right request-timeout knob - a local model gets a much longer
    budget (`performance.local_request_timeout`) than a cloud one
    (`performance.request_timeout`), and a call with no explicit timeout at
    all can hang on an ambiguous default instead of failing cleanly."""
    backend = str(model or "").split("/", 1)[0].strip().lower()
    api_base_low = str(api_base or "").lower()
    return backend in _LOCAL_MODEL_PREFIXES or any(
        h in api_base_low for h in ("localhost", "127.0.0.1", "0.0.0.0", ":11434")
    )


def get_version() -> str:
    """The installed package's own version — pyproject.toml is the one
    source of truth (read via package metadata, not retyped here), so a
    banner or endpoint calling this can't independently drift from it the
    way a hardcoded "vX.Y.Z" string does. "dev" (not a stale last-known
    number) is the honest fallback for a source checkout that was never
    `pip install`-ed."""
    try:
        from importlib.metadata import version as _pkg_version

        return _pkg_version("sympose")
    except Exception:
        return "dev"


class ConfigManager:
    """Manages master configuration loading, validation, and dynamic updates.

    Runtime defaults are not held here — `config_schema.build_default_config()`
    materialises them from the one declarative `SETTINGS` list, and `config.yaml`
    is layered on top."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> dict[str, Any]:
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
            elif value is None and isinstance(base.get(key), dict):
                # A bare `key:` with no sub-values in config.yaml (e.g. an
                # empty `performance:` section) parses to None, not {} -
                # without this guard it would replace the whole materialized
                # default subtree with None instead of leaving it untouched.
                continue
            else:
                base[key] = value

    def _apply_runtime_settings(self) -> None:
        """Applies loaded performance knobs to third-party libraries like LiteLLM and loads MCP registry."""
        if litellm is not None:
            perf = self.data.get("performance") or {}
            litellm.request_timeout = float(
                perf.get(
                    "request_timeout", default_for("performance.request_timeout")
                )
            )
            litellm.drop_params = bool(
                perf.get(
                    "drop_unsupported_params",
                    default_for("performance.drop_unsupported_params"),
                )
            )

        try:
            from sympose.mcp import mcp_registry

            mcp_registry.load_from_config(self.data)
        except Exception as e:
            logging.warning("Failed to load MCP servers from config: %s", e)

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
