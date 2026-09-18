"""
Vault and Sub-Agent Sandbox `Setting` declarations — one part of the
ADR-126 split of config_schema.py's SETTINGS tuple.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

VAULT = "Vault"
SUB_AGENT = "Sub-Agent Sandbox"

VAULT_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "vault.search_mode",
        "str",
        "direct",
        "Vault search backend.",
        VAULT,
        choices=("direct", "sqlite_fts", "semantic"),
    ),
    Setting(
        "vault.grounding_default",
        "str",
        "auto",
        "Vault-grounding enforcement when a persona sets no vault_grounding. "
        "auto = strict for local models, trust for cloud.",
        VAULT,
        choices=("auto", "strict", "trust"),
    ),
    Setting(
        "vault.daily_notes_folder",
        "str",
        "Daily",
        "Vault folder for daily notes.",
        VAULT,
    ),
    Setting(
        "vault.daily_notes_format",
        "str",
        "Daily/%Y/%m-%B/%Y-%m-%d.md",
        "strftime path for a daily note.",
        VAULT,
    ),
    Setting(
        "vault.ignore_folders",
        "list",
        [
            ".obsidian",
            ".git",
            "Attachments",
            "Drawings",
            ".trash",
        ],
        "Folders excluded from vault search and indexing.",
        VAULT,
    ),
    Setting(
        "vault.search_triggers",
        "list",
        [],
        "Extra keywords that flag a message as a vault query (added to the built-ins).",
        VAULT,
    ),
    Setting(
        "vault.manifest.enabled",
        "bool",
        True,
        "Maintain a materialized structural map of the vault (nodes, links, folders) "
        "under the workspace for the persona and the dashboard graph (ADR-078). Built "
        "lazily on first use; set false to disable entirely.",
        VAULT,
    ),
    Setting(
        "vault.manifest.check_debounce_seconds",
        "float",
        2.0,
        "Minimum seconds between vault-manifest freshness scans; 0 disables the debounce.",
        VAULT,
        minimum=0,
    ),
    Setting(
        "vault.manifest.max_nodes",
        "int",
        0,
        "Cap on vault-manifest nodes (0 = unlimited); guards pathological vaults.",
        VAULT,
        minimum=0,
    ),
    Setting(
        "vault.multi_writer_safety",
        "bool",
        False,
        "Enable the optimistic-concurrency guard (ADR-129): callers that "
        "pass expected_mtime to write_note/append_note/overwrite_note get "
        "a NOTE_CONFLICT instead of silently clobbering a file that "
        "changed since they last read it. Off by default so a single "
        "writer pays zero cost. Sync-mechanism-agnostic — no assumption "
        "about Obsidian Sync specifically; this guards against ANY two "
        "concurrent writers, on one machine or many.",
        VAULT,
    ),
)

SUB_AGENT_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "sub_agent.shell_allowlist",
        "list",
        [],
        "argv[0] allowlist for the sub-agent `run_command` tool (read-only commands only).",
        SUB_AGENT,
        live=False,
    ),
    Setting(
        "sub_agent.shell_command_timeout",
        "float",
        20.0,
        "Hard wall-clock cap on a single `run_command` execution, seconds.",
        SUB_AGENT,
        minimum=1,
    ),
    Setting(
        "sub_agent.request_timeout",
        "float",
        120.0,
        "A sub-agent's own LLM call timeout, seconds - one call per tool-use "
        "turn, up to max_sub_agent_tool_turns of them. Deliberately separate "
        "from performance.request_timeout: that one bounds a live, streamed "
        "chat reply's TTFT, but a sub-agent's report is delivered as a "
        "single block once the whole tool-calling loop finishes, so there's "
        "no TTFT reason to use the short cloud timeout even when its model "
        "is a cloud one.",
        SUB_AGENT,
        minimum=1,
    ),
    Setting(
        "sub_agent.unsupported_synthesis_min_words",
        "int",
        15,
        "Minimum word count before a sub-agent's synthesis is checked for "
        "verbatim overlap with what it actually retrieved (_content_unsupported) "
        "- below this, a reply is too short to reliably judge. Live-tuned once "
        "already (25 -> 15) after a real fabrication slipped under the original "
        "bar; expect to retune this in either direction as more live failures "
        "surface.",
        SUB_AGENT,
        minimum=1,
    ),
)
