"""
Unit tests for sympose.config_schema — the declarative config registry that
`/config`, `/config set` and `[CONFIG_SET]` are built on.
"""

import pytest

from sympose.config_schema import (
    SETTINGS, SECTIONS, get_setting, default_for, coerce, validate,
    global_settings, persona_settings,
)
from sympose.config import ConfigManager


class TestSchemaIntegrity:
    def test_keys_unique(self):
        keys = [s.key for s in SETTINGS]
        assert len(keys) == len(set(keys))

    def test_every_setting_has_a_known_section(self):
        for s in SETTINGS:
            assert s.section in SECTIONS

    def test_types_are_supported(self):
        for s in SETTINGS:
            assert s.type in ("int", "float", "bool", "str", "list")

    def test_default_matches_type(self):
        for s in SETTINGS:
            if s.default is None:
                continue
            expect = {"int": int, "float": (int, float), "bool": bool,
                      "str": str, "list": list}[s.type]
            assert isinstance(s.default, expect), f"{s.key} default {s.default!r} not {s.type}"

    def test_global_and_persona_partition(self):
        assert len(global_settings()) + len(persona_settings()) == len(SETTINGS)

    def test_schema_defaults_agree_with_ConfigManager_DEFAULT_CONFIG(self):
        """Where DEFAULT_CONFIG defines a key, the schema default must match it."""
        flat = {}

        def _flatten(d, prefix=""):
            for k, v in d.items():
                p = f"{prefix}{k}"
                if isinstance(v, dict):
                    _flatten(v, p + ".")
                else:
                    flat[p] = v

        _flatten(ConfigManager.DEFAULT_CONFIG)
        for key, val in flat.items():
            s = get_setting(key)
            if s is None:
                continue
            if s.default in (None, ""):
                continue  # schema "" / None = "unset, resolve elsewhere"
            assert s.default == val, f"{key}: schema {s.default!r} != DEFAULT_CONFIG {val!r}"


class TestCoerce:
    def test_int_float_bool_list(self):
        assert coerce(get_setting("performance.max_context_turns"), "20") == 20
        assert coerce(get_setting("performance.request_timeout"), "12.5") == 12.5
        assert coerce(get_setting("performance.stream"), "false") is False
        assert coerce(get_setting("performance.stream"), "on") is True
        assert coerce(get_setting("vault.ignore_folders"), "a, b ,c") == ["a", "b", "c"]

    def test_bad_number_raises_with_message(self):
        with pytest.raises(ValueError, match="not a valid int"):
            coerce(get_setting("performance.max_context_turns"), "lots")

    def test_bad_bool_raises(self):
        with pytest.raises(ValueError, match="boolean"):
            coerce(get_setting("performance.stream"), "maybe")


class TestValidate:
    def test_enum_rejected(self):
        ok, err = validate("vault.grounding_default", "loose")
        assert not ok and "auto" in err

    def test_enum_accepted(self):
        assert validate("vault.grounding_default", "strict") == (True, "")

    def test_range_rejected(self):
        ok, err = validate("performance.max_context_turns", 0)
        assert not ok and ">=" in err

    def test_unknown_key_passes(self):
        assert validate("totally.made.up", "x") == (True, "")


class TestConfigManagerSchemaFallback:
    def test_absent_key_falls_back_to_schema_default(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        assert cm.get("vault.grounding_default") == "auto"

    def test_explicit_default_still_wins(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        assert cm.get("vault.grounding_default", "trust") == "trust"

    def test_unknown_key_is_none(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        assert cm.get("no.such.key") is None

    def test_default_for_helper(self):
        assert default_for("performance.max_worker_tool_turns") == 8
        assert default_for("no.such.key") is None
