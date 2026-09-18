"""
The `Setting` dataclass — one row describing a runtime knob (key, type,
default, allowed values, description). Split out of config_schema.py
(ADR-126) so the per-section setting-list modules (config_settings_*.py) can
import it without an import cycle back to config_schema.py itself, which
concatenates their tuples into `SETTINGS`.

Standalone: imports nothing from `sympose`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Setting:
    key: str  # dotted path, e.g. "performance.stream"
    type: str  # int | float | bool | str | list | dict
    default: Any
    description: str
    section: str  # display grouping for /config
    choices: Sequence[Any] | None = None  # closed set of allowed values
    minimum: float | None = None
    maximum: float | None = None
    scope: str = "global"  # global | persona
    live: bool = True  # takes effect without a restart
