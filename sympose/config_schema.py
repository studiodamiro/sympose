"""
Declarative configuration schema for Sympose.

One place that names every runtime knob — its type, default, allowed values, and a
one-line description. `ConfigManager.get()` falls back to these defaults, `/config`
renders itself from this list, and `/config set` / `[CONFIG_SET]` validate against
it. Adding a knob = adding a `Setting` here (plus reading it where it matters).

Standalone by design: imports nothing from `sympose` so `config.py` can import it
at module load without a cycle.
"""

import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Setting:
    key: str                                  # dotted path, e.g. "performance.stream"
    type: str                                 # int | float | bool | str | list
    default: Any
    description: str
    section: str                              # display grouping for /config
    choices: Optional[Sequence[Any]] = None   # closed set of allowed values
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    scope: str = "global"                     # global | persona
    live: bool = True                         # takes effect without a restart


# --- ordered for /config display -------------------------------------------
SECTIONS: Tuple[str, ...] = (
    "Performance & Streaming",
    "Session & Memory",
    "Runtime",
    "Vault",
    "Worker Sandbox",
    "Persona (set in profiles/<handle>.yaml)",
)

SETTINGS: Tuple[Setting, ...] = (
    # --- Performance & Streaming -----------------------------------------
    Setting("performance.request_timeout", "float", 30.0,
            "Cloud-model HTTP timeout, seconds.", "Performance & Streaming", minimum=1),
    Setting("performance.local_request_timeout", "float", 120.0,
            "Local (ollama/…) model timeout, seconds.", "Performance & Streaming", minimum=1),
    Setting("performance.local_keep_alive", "str", None,
            "Ollama residency hint: -1 forever, 0 unload, '30m'. Unset = defer to OLLAMA_KEEP_ALIVE.",
            "Performance & Streaming"),
    Setting("performance.max_context_turns", "int", 15,
            "Conversation turns kept in the model context window.", "Performance & Streaming", minimum=1),
    Setting("performance.resume_context_turns", "int", 6,
            "Turns rehydrated when resuming a saved session.", "Performance & Streaming", minimum=0),
    Setting("performance.max_worker_tool_turns", "int", 8,
            "Tool-call budget for a sub-agent worker before a forced synthesis.",
            "Performance & Streaming", minimum=1),
    Setting("performance.max_consecutive_bot_turns", "int", 3,
            "Bot-to-bot reply streak cap in a Slack thread.", "Performance & Streaming", minimum=1),
    Setting("performance.slack_thread_context_limit", "int", 12,
            "Preceding Slack thread messages pulled into a turn's context.",
            "Performance & Streaming", minimum=0),
    Setting("performance.slack_max_concurrent", "int", 3,
            "Max concurrently-handled Slack messages.", "Performance & Streaming", minimum=1),
    Setting("performance.hygiene_workers", "int", 2,
            "Background hygiene thread-pool size (extraction, titling, compaction).",
            "Performance & Streaming", minimum=1, live=False),
    Setting("performance.drop_unsupported_params", "bool", True,
            "Silently drop model params a backend rejects (litellm.drop_params).",
            "Performance & Streaming"),
    Setting("performance.stream", "bool", True,
            "Stream model output token-by-token.", "Performance & Streaming"),
    Setting("performance.render_mode", "str", "hybrid",
            "Terminal render mode.", "Performance & Streaming",
            choices=("raw", "hybrid", "buffered")),

    # --- Session & Memory ----------------------------------------------
    Setting("session.exit_behavior.auto_save", "bool", False,
            "Auto-save the session on exit.", "Session & Memory"),
    Setting("session.exit_behavior.default_target", "str", "memory",
            "Where an auto-saved session goes.", "Session & Memory",
            choices=("memory", "vault", "both")),
    Setting("session.exit_behavior.clear_terminal", "bool", True,
            "Clear the terminal on exit.", "Session & Memory"),
    Setting("session.exit_behavior.obsidian_subfolder", "str", "Sessions",
            "Vault subfolder for archived sessions.", "Session & Memory"),
    Setting("session.exit_behavior.summarization_model", "str", "",
            "Model for session summaries; empty = the active chat model.", "Session & Memory"),
    Setting("memory.auto_compact", "bool", True,
            "Auto-compact working memory past the threshold.", "Session & Memory"),
    Setting("memory.compaction_threshold", "int", 25,
            "Working-memory line count that triggers compaction.", "Session & Memory", minimum=1),
    Setting("memory.extraction_timeout", "float", 8.0,
            "Timeout for the background memory extractor, seconds.", "Session & Memory", minimum=0),
    Setting("memory.user_profile_file", "str", "profiles/user_profile.md",
            "Path to the core user profile.", "Session & Memory", live=False),
    Setting("memory.shared_memory_file", "str", "profiles/_shared_memory.md",
            "Path to the shared team memory pool.", "Session & Memory", live=False),

    # --- Runtime ------------------------------------------------------
    Setting("runtime.default_persona", "str", "samantha",
            "Persona loaded at startup.", "Runtime"),
    Setting("runtime.profiles_dir", "str", "profiles",
            "Directory holding persona YAMLs.", "Runtime", live=False),

    # --- Vault ------------------------------------------------------
    Setting("vault.search_mode", "str", "direct",
            "Vault search backend.", "Vault", choices=("direct", "sqlite_fts", "semantic")),
    Setting("vault.grounding_default", "str", "auto",
            "Vault-grounding enforcement when a persona sets no vault_grounding. "
            "auto = strict for local models, trust for cloud.",
            "Vault", choices=("auto", "strict", "trust")),
    Setting("vault.daily_notes_folder", "str", "Daily",
            "Vault folder for daily notes.", "Vault"),
    Setting("vault.daily_notes_format", "str", "Daily/%Y/%m-%B/%Y-%m-%d.md",
            "strftime path for a daily note.", "Vault"),
    Setting("vault.ignore_folders", "list",
            [".obsidian", ".git", "Attachments", "Drawings", "Movies", ".trash", "dot-files"],
            "Folders excluded from vault search and indexing.", "Vault"),
    Setting("vault.search_triggers", "list", [],
            "Extra keywords that flag a message as a vault query (added to the built-ins).",
            "Vault"),

    # --- Worker Sandbox --------------------------------------------
    Setting("worker.shell_allowlist", "list", [],
            "argv[0] allowlist for the worker `run_command` tool (read-only commands only).",
            "Worker Sandbox", live=False),

    # --- Persona-scoped (edit the persona YAML, not /config) --------
    Setting("vault_grounding", "str", "auto",
            "Per-persona grounding: auto|strict|trust.", SECTIONS[5],
            choices=("auto", "strict", "trust"), scope="persona"),
    Setting("keep_alive", "str", "",
            "Per-persona Ollama keep_alive override.", SECTIONS[5], scope="persona"),
    Setting("share_memory", "bool", False,
            "Write to the shared team memory pool instead of private memory.",
            SECTIONS[5], scope="persona"),
    Setting("temperature", "float", None,
            "Sampling temperature.", SECTIONS[5], minimum=0, maximum=2, scope="persona"),
    Setting("model", "str", "",
            "litellm model id (e.g. gemini/gemini-3.6-flash, ollama/llama3.1:8b).",
            SECTIONS[5], scope="persona"),
    Setting("api_base", "str", "",
            "Custom API base URL for the persona's model.", SECTIONS[5], scope="persona"),
)

_BY_KEY = {s.key: s for s in SETTINGS}
_SENTINEL = object()


def get_setting(key: str) -> Optional[Setting]:
    return _BY_KEY.get(key)


def default_for(key: str) -> Any:
    s = _BY_KEY.get(key)
    return s.default if s is not None else None


def global_settings() -> list:
    return [s for s in SETTINGS if s.scope == "global"]


def build_default_config() -> Dict[str, Any]:
    """Materialise every global setting's default into the nested dict shape
    `ConfigManager` layers `config.yaml` onto. This is the *only* source of
    runtime defaults — there is no hand-maintained mirror. A fresh dict (with
    independent list/dict values) is returned on every call, so callers may
    mutate it freely."""
    out: Dict[str, Any] = {}
    for s in SETTINGS:
        if s.scope != "global" or s.default is None:
            continue
        node = out
        *branches, leaf = s.key.split(".")
        for part in branches:
            node = node.setdefault(part, {})
        node[leaf] = copy.deepcopy(s.default)
    return out


def persona_settings() -> list:
    return [s for s in SETTINGS if s.scope == "persona"]


def coerce(setting: Setting, raw: Any) -> Any:
    """Turn a raw CLI/tag string into the setting's declared type.
    Raises ValueError with a human message on a bad value."""
    if not isinstance(raw, str):
        return raw
    r = raw.strip()
    try:
        if setting.type == "int":
            return int(r)
        if setting.type == "float":
            return float(r)
        if setting.type == "bool":
            low = r.lower()
            if low in ("true", "1", "yes", "on"):
                return True
            if low in ("false", "0", "no", "off"):
                return False
            raise ValueError(f"`{raw}` is not a boolean (use true/false)")
        if setting.type == "list":
            return [p.strip() for p in r.split(",") if p.strip()]
        return r  # str
    except ValueError as e:
        if setting.type in ("int", "float"):
            raise ValueError(f"`{raw}` is not a valid {setting.type}") from e
        raise


def validate(key: str, value: Any) -> Tuple[bool, str]:
    """(-> ok, error). Unknown keys pass (backward compatible) so the caller
    decides whether to reject them."""
    s = _BY_KEY.get(key)
    if s is None:
        return True, ""
    if value is None:
        return True, ""
    if s.choices is not None and value not in s.choices:
        return False, f"must be one of: {', '.join(map(str, s.choices))}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if s.minimum is not None and value < s.minimum:
            return False, f"must be >= {s.minimum}"
        if s.maximum is not None and value > s.maximum:
            return False, f"must be <= {s.maximum}"
    return True, ""
