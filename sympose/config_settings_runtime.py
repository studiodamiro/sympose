"""
Session & Memory and Runtime `Setting` declarations — one part of the
ADR-126 split of config_schema.py's SETTINGS tuple.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

SESS = "Session & Memory"
RUN = "Runtime"

SESSION_RUNTIME_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "session.exit_behavior.auto_save",
        "bool",
        False,
        "Auto-save the session on exit.",
        SESS,
    ),
    Setting(
        "session.exit_behavior.default_target",
        "str",
        "memory",
        "Where an auto-saved session goes.",
        SESS,
        choices=("memory", "vault", "both"),
    ),
    Setting(
        "session.exit_behavior.clear_terminal",
        "bool",
        True,
        "Clear the terminal on exit.",
        SESS,
    ),
    Setting(
        "session.exit_behavior.obsidian_subfolder",
        "str",
        "Sessions",
        "Vault subfolder for archived sessions.",
        SESS,
    ),
    Setting(
        "session.exit_behavior.summarization_model",
        "str",
        "",
        "Model for session summaries; empty = the active chat model.",
        SESS,
    ),
    Setting(
        "session.exit_behavior.title_timeout",
        "float",
        4.0,
        "Timeout for the background session-auto-title generator, seconds.",
        SESS,
        minimum=0,
    ),
    Setting(
        "memory.auto_compact",
        "bool",
        True,
        "Auto-compact working memory past the threshold.",
        SESS,
    ),
    Setting(
        "memory.compaction_threshold",
        "int",
        25,
        "Working-memory line count that triggers compaction.",
        SESS,
        minimum=1,
    ),
    Setting(
        "memory.extraction_timeout",
        "float",
        8.0,
        "Timeout for the background memory extractor, seconds.",
        SESS,
        minimum=0,
    ),
    Setting(
        "memory.user_profile_file",
        "str",
        "profiles/user_profile.md",
        "Path to the core user profile.",
        SESS,
        live=False,
    ),
    Setting(
        "memory.shared_memory_file",
        "str",
        "profiles/_shared_memory.md",
        "Path to the shared team memory pool.",
        SESS,
        live=False,
    ),
    Setting(
        "runtime.default_persona", "str", "samantha", "Persona loaded at startup.", RUN
    ),
    Setting(
        "runtime.profiles_dir",
        "str",
        "profiles",
        "Directory holding persona YAMLs.",
        RUN,
        live=False,
    ),
)
