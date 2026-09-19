"""
Unit tests for sympose.model_capability — the ADR-127 capability-tier
resolver. Pure functions, no config reads: every test passes tier_order/
tiers explicitly, mirroring model_router.py's own test style.
"""

import pytest

from sympose import model_capability

ORDER = ["basic", "standard", "high"]


class TestTierIndex:
    def test_known_names_resolve_to_position(self):
        assert model_capability.tier_index(ORDER, "basic") == 0
        assert model_capability.tier_index(ORDER, "standard") == 1
        assert model_capability.tier_index(ORDER, "high") == 2

    def test_unknown_name_defaults_to_zero(self):
        assert model_capability.tier_index(ORDER, "nonexistent") == 0

    def test_none_defaults_to_zero(self):
        assert model_capability.tier_index(ORDER, None) == 0


class TestTierOf:
    def test_assigned_model_returns_its_tier(self):
        tiers = {"gemini/gemini-3.6-flash": "standard"}
        assert model_capability.tier_of(ORDER, tiers, "gemini/gemini-3.6-flash") == "standard"

    def test_unassigned_model_defaults_to_lowest_tier(self):
        assert model_capability.tier_of(ORDER, {}, "some/unlisted-model") == "basic"

    def test_assignment_to_an_unknown_tier_name_falls_back_to_lowest(self):
        tiers = {"some/model": "legendary"}
        assert model_capability.tier_of(ORDER, tiers, "some/model") == "basic"

    def test_empty_tier_order_returns_empty_string_not_a_guessed_name(self):
        """An empty tier_order has no lowest tier to name — this must not
        hardcode a schema-default literal, since tier_index already treats
        any unrecognized name (including "") as tier 0 regardless."""
        assert model_capability.tier_of([], {}, "some/model") == ""


class TestStrictestTier:
    def test_none_and_none_is_none(self):
        assert model_capability.strictest_tier(ORDER, None, None) is None

    def test_one_none_returns_the_other(self):
        assert model_capability.strictest_tier(ORDER, "high", None) == "high"
        assert model_capability.strictest_tier(ORDER, None, "basic") == "basic"

    def test_returns_the_higher_of_two_declared_tiers_either_order(self):
        assert model_capability.strictest_tier(ORDER, "basic", "high") == "high"
        assert model_capability.strictest_tier(ORDER, "high", "basic") == "high"

    def test_equal_tiers_returns_that_tier(self):
        assert model_capability.strictest_tier(ORDER, "standard", "standard") == "standard"


class TestClears:
    def test_no_minimum_always_clears(self):
        assert model_capability.clears(ORDER, {}, "any/model", None) is True

    def test_capable_local_model_clears_a_high_bar(self):
        tiers = {"ollama/qwen2.5-32b-instruct": "high"}
        assert model_capability.clears(ORDER, tiers, "ollama/qwen2.5-32b-instruct", "high") is True

    def test_unassigned_cloud_model_fails_a_high_bar(self):
        # No local=capable/cloud=incapable assumption: an *unassigned* model
        # of any kind defaults to the lowest tier and fails a real floor.
        assert model_capability.clears(ORDER, {}, "gemini/gemini-3.6-flash", "high") is False

    def test_model_exactly_at_the_minimum_clears(self):
        tiers = {"some/model": "standard"}
        assert model_capability.clears(ORDER, tiers, "some/model", "standard") is True

    def test_unrecognized_minimum_fails_safe_to_the_strictest_tier(self):
        """Regression: a typo'd/renamed-away `minimum` used to be treated
        as tier 0 (no requirement at all), so even the weakest model
        cleared it. It must instead behave as the strictest declared tier
        — nothing but the top tier clears a misconfigured requirement."""
        tiers = {"cheap/model": "basic", "capable/model": "high"}
        assert model_capability.clears(ORDER, tiers, "cheap/model", "hgih") is False
        assert model_capability.clears(ORDER, tiers, "capable/model", "hgih") is True

    def test_unrecognized_minimum_raises_when_strict(self):
        with pytest.raises(ValueError):
            model_capability.clears(ORDER, {}, "any/model", "hgih", strict=True)


class TestResolveCapable:
    def test_no_minimum_returns_first_candidate(self):
        assert model_capability.resolve_capable(ORDER, {}, ["a", "b"], None) == "a"

    def test_returns_first_candidate_in_order_that_clears_the_bar(self):
        tiers = {"cheap/model": "basic", "capable/model": "high"}
        result = model_capability.resolve_capable(
            ORDER, tiers, ["cheap/model", "capable/model"], "high"
        )
        assert result == "capable/model"

    def test_unrecognized_minimum_still_picks_a_top_tier_candidate(self):
        tiers = {"cheap/model": "basic", "capable/model": "high"}
        result = model_capability.resolve_capable(
            ORDER, tiers, ["cheap/model", "capable/model"], "hgih"
        )
        assert result == "capable/model"

    def test_prefers_cost_order_when_multiple_candidates_clear(self):
        tiers = {"first/model": "standard", "second/model": "high"}
        result = model_capability.resolve_capable(
            ORDER, tiers, ["first/model", "second/model"], "standard"
        )
        assert result == "first/model"

    def test_fails_open_to_highest_tier_when_none_clear(self):
        tiers = {"weak/model": "basic", "less_weak/model": "standard"}
        result = model_capability.resolve_capable(
            ORDER, tiers, ["weak/model", "less_weak/model"], "high"
        )
        assert result == "less_weak/model"

    def test_empty_candidates_raises(self):
        with pytest.raises(ValueError):
            model_capability.resolve_capable(ORDER, {}, [], "high")
