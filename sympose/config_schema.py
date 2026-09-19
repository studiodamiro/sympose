"""
Declarative configuration schema for Sympose — one place naming every runtime
knob (type, default, allowed values, one-line description). `ConfigManager.get()`
falls back to these defaults, `/config` renders itself from this list, and
`/config set` / `[CONFIG_SET]` / `/persona set` validate against it. Adding a knob
= adding a `Setting` here (plus reading it where it matters).

The `Setting` entries themselves live in per-section modules (config_setting.py
for the dataclass, config_settings_{performance,runtime,vault,persona}.py for
the declarations, ADR-126) to keep every file under the project's 200-LOC
ceiling; this file owns the lookup/validation logic and concatenates their
tuples into `SETTINGS`. `Setting`/`SETTINGS`/`SECTIONS` are re-exported here
unchanged, so every existing caller (`config.py`, `profiles.py`, `commands.py`,
`config_reference.py`, etc.) is unaffected.

Standalone: imports nothing from `sympose` except the section modules above
(themselves standalone), so `config.py` can import it at module load without
a cycle.
"""

import copy
from typing import Any

from sympose.config_setting import Setting
from sympose.config_settings_models import MODEL_SETTINGS, MODELS
from sympose.config_settings_performance import PERF, PERFORMANCE_SETTINGS
from sympose.config_settings_persona import PERSONA, PERSONA_SETTINGS
from sympose.config_settings_runtime import RUN, SESS, SESSION_RUNTIME_SETTINGS
from sympose.config_settings_vault import SUB_AGENT, SUB_AGENT_SETTINGS, VAULT, VAULT_SETTINGS
from sympose.config_settings_wiki import WIKI, WIKI_SETTINGS

# Ordered for /config display.
SECTIONS: tuple[str, ...] = (
    PERF,
    SESS,
    RUN,
    VAULT,
    SUB_AGENT,
    MODELS,
    WIKI,
    PERSONA,
)

SETTINGS: tuple[Setting, ...] = (
    PERFORMANCE_SETTINGS
    + SESSION_RUNTIME_SETTINGS
    + VAULT_SETTINGS
    + SUB_AGENT_SETTINGS
    + MODEL_SETTINGS
    + WIKI_SETTINGS
    + PERSONA_SETTINGS
)

_BY_KEY = {s.key: s for s in SETTINGS}


def get_setting(key: str) -> Setting | None:
    return _BY_KEY.get(key)


def default_for(key: str) -> Any:
    s = _BY_KEY.get(key)
    return s.default if s is not None else None


def global_settings() -> list:
    return [s for s in SETTINGS if s.scope == "global"]


def persona_settings() -> list:
    return [s for s in SETTINGS if s.scope == "persona"]


def build_default_config() -> dict[str, Any]:
    """Materialise every global setting's default into the nested dict shape
    `ConfigManager` layers `config.yaml` onto. The only source of runtime
    defaults — no hand-maintained mirror. A fresh, independently-owned dict is
    returned per call, so callers may mutate it freely. A `None` default is
    omitted (it means "unset — resolve elsewhere")."""
    out: dict[str, Any] = {}
    for s in SETTINGS:
        if s.scope != "global" or s.default is None:
            continue
        node = out
        *branches, leaf = s.key.split(".")
        for part in branches:
            node = node.setdefault(part, {})
        node[leaf] = copy.deepcopy(s.default)
    return out


def _coerce_bool(raw: str, r: str) -> bool:
    low = r.lower()
    if low in ("true", "1", "yes", "on"):
        return True
    if low in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"`{raw}` is not a boolean (use true/false)")


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
            return _coerce_bool(raw, r)
        if setting.type == "list":
            return [p.strip() for p in r.split(",") if p.strip()]
        if setting.type == "dict":
            raise ValueError("edit config.yaml directly for this key (not a single-value set)")
        return r  # str
    except ValueError as e:
        if setting.type in ("int", "float"):
            raise ValueError(f"`{raw}` is not a valid {setting.type}") from e
        raise


def validate(key: str, value: Any) -> tuple[bool, str]:
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
