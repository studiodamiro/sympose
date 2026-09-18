"""
LLM Wiki layer `Setting` declarations (ADR-132) — the opt-in Tier-3
raw-sources/wiki/schema convention. Empty `wiki.root` (the default)
disables the whole feature; nothing here has any effect until a user sets
it.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

WIKI = "LLM Wiki (Tier 3, opt-in)"

WIKI_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "wiki.root",
        "str",
        "",
        "Vault-relative root folder for the AI-owned LLM-wiki subtree "
        "(ADR-132). Empty (default) disables the wiki layer entirely — no "
        "wiki_ingest/wiki_lint skill has anywhere to act until this is set.",
        WIKI,
    ),
    Setting(
        "wiki.raw_sources_subdir",
        "str",
        "Sources",
        "Subfolder under wiki.root holding immutable original sources — "
        "read by wiki skills, never edited.",
        WIKI,
    ),
    Setting(
        "wiki.schema_file",
        "str",
        "WIKI.md",
        "Filename at wiki.root: the navigation schema explaining how the "
        "wiki is structured, seeded once and safe to hand-edit afterward.",
        WIKI,
    ),
    Setting(
        "wiki.log_file",
        "str",
        "log.md",
        "Filename at wiki.root: chronological, append-only ingest/lint "
        "audit trail.",
        WIKI,
    ),
)
