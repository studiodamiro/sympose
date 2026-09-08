"""
Declarative configuration schema for Sympose — one place naming every runtime
knob (type, default, allowed values, one-line description). `ConfigManager.get()`
falls back to these defaults, `/config` renders itself from this list, and
`/config set` / `[CONFIG_SET]` / `/persona set` validate against it. Adding a knob
= adding a `Setting` here (plus reading it where it matters).

Standalone: imports nothing from `sympose`, so `config.py` can import it at module
load without a cycle.
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


_PERF, _SESS, _RUN, _VAULT, _WORK, _PERSONA = (
    "Performance & Streaming", "Session & Memory", "Runtime",
    "Vault", "Worker Sandbox", "Persona (set in profiles/<handle>.yaml)",
)

# Ordered for /config display.
SECTIONS: Tuple[str, ...] = (_PERF, _SESS, _RUN, _VAULT, _WORK, _PERSONA)

SETTINGS: Tuple[Setting, ...] = (
    Setting("performance.request_timeout", "float", 30.0,
            "Cloud-model HTTP timeout, seconds.", _PERF, minimum=1),
    Setting("performance.local_request_timeout", "float", 120.0,
            "Local (ollama/…) model timeout, seconds.", _PERF, minimum=1),
    Setting("performance.local_keep_alive", "str", None,
            "Ollama residency hint: -1 forever, 0 unload, '30m'. Unset = defer to OLLAMA_KEEP_ALIVE.", _PERF),
    Setting("performance.max_context_turns", "int", 15,
            "Conversation turns kept in the model context window.", _PERF, minimum=1),
    Setting("performance.resume_context_turns", "int", 6,
            "Turns rehydrated when resuming a saved session.", _PERF, minimum=0),
    Setting("performance.max_worker_tool_turns", "int", 8,
            "Tool-call budget for a sub-agent worker before a forced synthesis.", _PERF, minimum=1),
    Setting("performance.max_consecutive_bot_turns", "int", 3,
            "Bot-to-bot reply streak cap in a Slack thread.", _PERF, minimum=1),
    Setting("performance.slack_thread_context_limit", "int", 12,
            "Preceding Slack thread messages pulled into a turn's context.", _PERF, minimum=0),
    Setting("performance.slack_max_concurrent", "int", 3,
            "Max concurrently-handled Slack messages.", _PERF, minimum=1),
    Setting("performance.hygiene_workers", "int", 2,
            "Background hygiene thread-pool size (extraction, titling, compaction).", _PERF, minimum=1, live=False),
    Setting("performance.drop_unsupported_params", "bool", True,
            "Silently drop model params a backend rejects (litellm.drop_params).", _PERF),
    Setting("performance.stream", "bool", True, "Stream model output token-by-token.", _PERF),
    Setting("performance.render_mode", "str", "hybrid",
            "Terminal render mode.", _PERF, choices=("raw", "hybrid", "buffered")),

    Setting("session.exit_behavior.auto_save", "bool", False, "Auto-save the session on exit.", _SESS),
    Setting("session.exit_behavior.default_target", "str", "memory",
            "Where an auto-saved session goes.", _SESS, choices=("memory", "vault", "both")),
    Setting("session.exit_behavior.clear_terminal", "bool", True, "Clear the terminal on exit.", _SESS),
    Setting("session.exit_behavior.obsidian_subfolder", "str", "Sessions",
            "Vault subfolder for archived sessions.", _SESS),
    Setting("session.exit_behavior.summarization_model", "str", "",
            "Model for session summaries; empty = the active chat model.", _SESS),
    Setting("memory.auto_compact", "bool", True, "Auto-compact working memory past the threshold.", _SESS),
    Setting("memory.compaction_threshold", "int", 25,
            "Working-memory line count that triggers compaction.", _SESS, minimum=1),
    Setting("memory.extraction_timeout", "float", 8.0,
            "Timeout for the background memory extractor, seconds.", _SESS, minimum=0),
    Setting("memory.user_profile_file", "str", "profiles/user_profile.md",
            "Path to the core user profile.", _SESS, live=False),
    Setting("memory.shared_memory_file", "str", "profiles/_shared_memory.md",
            "Path to the shared team memory pool.", _SESS, live=False),

    Setting("runtime.default_persona", "str", "samantha", "Persona loaded at startup.", _RUN),
    Setting("runtime.profiles_dir", "str", "profiles",
            "Directory holding persona YAMLs.", _RUN, live=False),

    Setting("vault.search_mode", "str", "direct",
            "Vault search backend.", _VAULT, choices=("direct", "sqlite_fts", "semantic")),
    Setting("vault.grounding_default", "str", "auto",
            "Vault-grounding enforcement when a persona sets no vault_grounding. "
            "auto = strict for local models, trust for cloud.", _VAULT, choices=("auto", "strict", "trust")),
    Setting("vault.daily_notes_folder", "str", "Daily", "Vault folder for daily notes.", _VAULT),
    Setting("vault.daily_notes_format", "str", "Daily/%Y/%m-%B/%Y-%m-%d.md",
            "strftime path for a daily note.", _VAULT),
    Setting("vault.ignore_folders", "list",
            [".obsidian", ".git", "Attachments", "Drawings", "Movies", ".trash", "dot-files"],
            "Folders excluded from vault search and indexing.", _VAULT),
    Setting("vault.search_triggers", "list", [],
            "Extra keywords that flag a message as a vault query (added to the built-ins).", _VAULT),
    Setting("vault.manifest.enabled", "bool", False,
            "Maintain a materialized structural map of the vault (nodes, links, folders) "
            "under the workspace for the agent and the dashboard graph (ADR-078).", _VAULT),
    Setting("vault.manifest.check_debounce_seconds", "float", 2.0,
            "Minimum seconds between vault-manifest freshness scans; 0 disables the debounce.",
            _VAULT, minimum=0),
    Setting("vault.manifest.max_nodes", "int", 0,
            "Cap on vault-manifest nodes (0 = unlimited); guards pathological vaults.",
            _VAULT, minimum=0),

    Setting("worker.shell_allowlist", "list", [],
            "argv[0] allowlist for the worker `run_command` tool (read-only commands only).", _WORK, live=False),

    # Persona-scoped — set with `/persona set @<handle> <key> <value>`, not /config.
    Setting("vault_grounding", "str", "auto",
            "Per-persona grounding: auto|strict|trust.", _PERSONA,
            choices=("auto", "strict", "trust"), scope="persona"),
    Setting("keep_alive", "str", "",
            "Per-persona Ollama keep_alive override.", _PERSONA, scope="persona"),
    Setting("share_memory", "bool", False,
            "Write to the shared team memory pool instead of private memory.", _PERSONA, scope="persona"),
    Setting("temperature", "float", None,
            "Sampling temperature.", _PERSONA, minimum=0, maximum=2, scope="persona"),
    Setting("model", "str", "",
            "litellm model id (e.g. gemini/gemini-3.6-flash, ollama/llama3.1:8b).", _PERSONA, scope="persona"),
    Setting("api_base", "str", "",
            "Custom API base URL for the persona's model.", _PERSONA, scope="persona"),
)

_BY_KEY = {s.key: s for s in SETTINGS}


def get_setting(key: str) -> Optional[Setting]:
    return _BY_KEY.get(key)


def default_for(key: str) -> Any:
    s = _BY_KEY.get(key)
    return s.default if s is not None else None


def global_settings() -> list:
    return [s for s in SETTINGS if s.scope == "global"]


def persona_settings() -> list:
    return [s for s in SETTINGS if s.scope == "persona"]


def build_default_config() -> Dict[str, Any]:
    """Materialise every global setting's default into the nested dict shape
    `ConfigManager` layers `config.yaml` onto. The only source of runtime
    defaults — no hand-maintained mirror. A fresh, independently-owned dict is
    returned per call, so callers may mutate it freely. A `None` default is
    omitted (it means "unset — resolve elsewhere")."""
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
    if s is None or value is None:
        return True, ""
    if s.choices is not None and value not in s.choices:
        return False, f"must be one of: {', '.join(map(str, s.choices))}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if s.minimum is not None and value < s.minimum:
            return False, f"must be >= {s.minimum}"
        if s.maximum is not None and value > s.maximum:
            return False, f"must be <= {s.maximum}"
    return True, ""
