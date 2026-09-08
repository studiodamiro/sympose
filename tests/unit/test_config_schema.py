"""
Unit tests for sympose.config_schema — the declarative config registry that
`/config`, `/config set` and `[CONFIG_SET]` are built on.
"""

from pathlib import Path

import pytest

import yaml

from sympose.config_schema import (
    SETTINGS, SECTIONS, get_setting, default_for, coerce, validate,
    global_settings, persona_settings, build_default_config,
)
from sympose.config_reference import render_reference_md
from sympose.bootstrap import render_seed_config
from sympose.config import ConfigManager

_REFERENCE_DOC = Path(__file__).resolve().parents[2] / "docs/wiki/reference/configuration.md"


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

    def test_no_hand_maintained_default_mirror(self):
        """The schema is the only source of runtime defaults — nothing shadows it."""
        assert not hasattr(ConfigManager, "DEFAULT_CONFIG")


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        p = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, p + "."))
        else:
            out[p] = v
    return out


class TestBuiltDefaults:
    def test_materialised_defaults_match_the_schema(self):
        flat = _flatten(build_default_config())
        # every non-None global default is present, with its declared value
        expected = {s.key: s.default for s in global_settings() if s.default is not None}
        assert flat == expected

    def test_none_defaults_are_omitted_not_nulled(self):
        """A None default means 'unset' — it must not land as an explicit key."""
        flat = _flatten(build_default_config())
        for s in global_settings():
            if s.default is None:
                assert s.key not in flat

    def test_fresh_ConfigManager_resolves_every_global_key_to_its_default(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        for s in global_settings():
            assert cm.get(s.key) == default_for(s.key), s.key

    def test_returned_dict_is_independent_per_call(self):
        a = build_default_config()
        a["vault"]["ignore_folders"].append("__mutated__")
        assert "__mutated__" not in build_default_config()["vault"]["ignore_folders"]


class TestSeedConfig:
    def test_seed_parses_and_holds_only_known_keys(self):
        data = yaml.safe_load(render_seed_config())
        for key in _flatten(data):
            assert get_setting(key) is not None, f"seed config.yaml has unknown key {key}"

    def test_seed_round_trips_to_the_built_defaults(self):
        assert yaml.safe_load(render_seed_config()) == build_default_config()


class TestReferenceDoc:
    def test_committed_doc_is_current(self):
        """docs/wiki/reference/configuration.md is generated from SETTINGS.
        Regenerate: python -m sympose.config_reference > docs/wiki/reference/configuration.md"""
        assert _REFERENCE_DOC.read_text(encoding="utf-8") == render_reference_md(), (
            "configuration.md is stale — regenerate with "
            "`python -m sympose.config_reference > docs/wiki/reference/configuration.md`"
        )

    def test_every_global_key_is_documented(self):
        body = _REFERENCE_DOC.read_text(encoding="utf-8")
        for s in global_settings():
            assert f"`{s.key}`" in body


class TestCompleterKeyLists:
    """The Tab-completer derives its key lists from the schema — guard against
    a hand-maintained copy creeping back in."""

    def test_completer_lists_track_the_schema(self):
        from sympose.completer import SymposeCompleter

        assert SymposeCompleter.CONFIG_KEYS == [s.key for s in global_settings()]
        assert SymposeCompleter.PERSONA_KEYS == [s.key for s in persona_settings()]


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

    def test_explicit_default_only_applies_to_genuinely_absent_keys(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        # a materialised key ignores the arg and returns its schema default
        assert cm.get("vault.grounding_default", "trust") == "auto"
        # an unknown key, and a None-default schema key, fall through to the arg
        assert cm.get("no.such.key", "x") == "x"
        assert cm.get("performance.local_keep_alive", "-1") == "-1"

    def test_unknown_key_is_none(self, tmp_path):
        cm = ConfigManager(str(tmp_path / "none.yaml"))
        assert cm.get("no.such.key") is None

    def test_default_for_helper(self):
        assert default_for("performance.max_worker_tool_turns") == 8
        assert default_for("no.such.key") is None
