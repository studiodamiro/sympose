"""
Persona-scoped `Setting` declarations (set in profiles/<handle>.yaml, not
config.yaml) — one part of the ADR-126 split of config_schema.py's SETTINGS
tuple.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

PERSONA = "Persona (set in profiles/<handle>.yaml)"

# Set with `/persona set @<handle> <key> <value>`, not /config.
PERSONA_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "vault_grounding",
        "str",
        "auto",
        "Per-persona grounding: auto|strict|trust.",
        PERSONA,
        choices=("auto", "strict", "trust"),
        scope="persona",
    ),
    Setting(
        "keep_alive",
        "str",
        "",
        "Per-persona Ollama keep_alive override.",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "share_memory",
        "bool",
        False,
        "Write to the shared team memory pool instead of private memory.",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "temperature",
        "float",
        None,
        "Sampling temperature.",
        PERSONA,
        minimum=0,
        maximum=2,
        scope="persona",
    ),
    Setting(
        "model",
        "str",
        "",
        "litellm model id (e.g. gemini/gemini-3.6-flash, ollama/llama3.1:8b).",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "local_model",
        "str",
        "",
        "Ollama model id for SIMPLE-tier messages (ADR-122) — definitions, "
        "quick math, a plain greeting. Empty = routing disabled, every "
        "message goes to `model` as today. Meaningless (leave unset) for a "
        "persona whose `model` is already local — there's no cheaper tier "
        "to route to, and no cloud fallback should ever fire for them.",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "capability_min_tier",
        "str",
        "",
        "Opt-in (ADR-135): route by declared capability tier "
        "(models.capability_tier_order/capability_tiers, ADR-127) instead "
        "of ADR-122's SIMPLE-message heuristic — every message this "
        "persona sends (not just short/trivial ones) routes to local_model "
        "whenever its declared tier clears this floor, falling back to "
        "`model` otherwise. Empty (default) = today's SIMPLE-message-only "
        "behavior, unchanged. Meaningless without local_model also set.",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "api_base",
        "str",
        "",
        "Custom API base URL for the persona's model.",
        PERSONA,
        scope="persona",
    ),
    Setting(
        "lint_auto_fix",
        "bool",
        False,
        "ADR-134: when this persona runs the wiki_lint skill, allow it to "
        "edit flagged pages directly under wiki.root instead of only "
        "logging findings to log.md. Off by default — user-trusted opt-in, "
        "your call whether to trust this persona to self-correct its own "
        "wiki pages. Has no effect on a persona without the wiki_lint "
        "skill, or when wiki.root is unset.",
        PERSONA,
        scope="persona",
    ),
)
