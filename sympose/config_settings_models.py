"""
Model Capability Tier `Setting` declarations (ADR-127) — the routing axis
that lets a model, local or cloud, be judged by whether it clears a
declared capability floor for a given operation, independent of where it
runs.

Standalone: imports nothing from `sympose` except the `Setting` dataclass
itself, so config_schema.py can import this without a cycle.
"""

from sympose.config_setting import Setting

MODELS = "Model Capability Tiers"

MODEL_SETTINGS: tuple[Setting, ...] = (
    Setting(
        "models.capability_tier_order",
        "list",
        ["basic", "standard", "high"],
        "Ordered least-to-most-capable tier names for capability-based "
        "routing (ADR-127) — position in this list is what's compared, "
        "not the label text. A separate axis from local-vs-cloud "
        "(ADR-122): a sufficiently capable local model can clear a "
        "'high' requirement, and a cloud model can be assigned 'basic'.",
        MODELS,
    ),
    Setting(
        "models.capability_tiers",
        "dict",
        {},
        "Explicit model-id -> tier-name assignment (value must be one of "
        "models.capability_tier_order). A model with no entry here "
        "defaults to the lowest declared tier — conservative by default, "
        "same bias as ADR-122's is_simple_message. Edit config.yaml "
        "directly (dict, not settable via `/config set`), e.g.: "
        '{"ollama/qwen2.5-32b-instruct": "high", '
        '"gemini/gemini-3.6-flash": "standard"}.',
        MODELS,
    ),
)
