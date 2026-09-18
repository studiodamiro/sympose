"""
Performance & Streaming `Setting` declarations — one part of the ADR-126
split of config_schema.py's SETTINGS tuple.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

PERF = "Performance & Streaming"

PERFORMANCE_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "performance.request_timeout",
        "float",
        30.0,
        "Cloud-model HTTP timeout, seconds.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.local_request_timeout",
        "float",
        120.0,
        "Local (ollama/…) model timeout, seconds.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.local_keep_alive",
        "str",
        None,
        "Ollama residency hint: -1 forever, 0 unload, '30m'. Unset = defer to OLLAMA_KEEP_ALIVE.",
        PERF,
    ),
    Setting(
        "performance.local_model_keep_alive",
        "dict",
        {},
        "Per-model Ollama residency override, keyed by exact model id (e.g. "
        "\"ollama/llama3.1:8b\": \"30m\"). Wins over a persona's own "
        "keep_alive and local_keep_alive above — the right place to set "
        "this once two or more personas share the same local model, since "
        "keep_alive is a property of the loaded model, not the persona "
        "calling it. Edit config.yaml directly; not settable via `/config set`.",
        PERF,
    ),
    Setting(
        "performance.max_context_turns",
        "int",
        15,
        "Conversation turns kept in the model context window.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.resume_context_turns",
        "int",
        6,
        "Turns rehydrated when resuming a saved session.",
        PERF,
        minimum=0,
    ),
    Setting(
        "performance.max_sub_agent_tool_turns",
        "int",
        8,
        "Tool-call budget for a sub-agent before a forced synthesis.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.max_consecutive_bot_turns",
        "int",
        3,
        "Bot-to-bot reply streak cap in a Slack thread.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.slack_thread_context_limit",
        "int",
        12,
        "Preceding Slack thread messages pulled into a turn's context.",
        PERF,
        minimum=0,
    ),
    Setting(
        "performance.slack_max_concurrent",
        "int",
        3,
        "Max concurrently-handled Slack messages.",
        PERF,
        minimum=1,
    ),
    Setting(
        "performance.hygiene_workers",
        "int",
        2,
        "Background hygiene thread-pool size (extraction, titling, compaction).",
        PERF,
        minimum=1,
        live=False,
    ),
    Setting(
        "performance.drop_unsupported_params",
        "bool",
        True,
        "Silently drop model params a backend rejects (litellm.drop_params).",
        PERF,
    ),
    Setting(
        "performance.stream", "bool", True, "Stream model output token-by-token.", PERF
    ),
    Setting(
        "performance.render_mode",
        "str",
        "hybrid",
        "Terminal render mode.",
        PERF,
        choices=("raw", "hybrid", "buffered"),
    ),
    Setting(
        "performance.local_simple_max_tokens",
        "int",
        200,
        "Response length cap for a SIMPLE-tier reply routed to a persona's "
        "local_model (ADR-122). Bounds worst-case wait independent of "
        "hardware/warm state — the local model's tokens/sec doesn't change, "
        "so a short cap is what actually keeps a trivial reply fast.",
        PERF,
        minimum=1,
    ),
)
