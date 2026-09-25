"""Tests for sympose.engine.helper_limit (docs/decisions/007): how many tokens the small
background calls may write, by kind of model, and the `cloud_helper_limit` knob."""

import pytest

from sympose import settings_store
from sympose.engine import helper_limit

CLOUD = "gemini/gemini-flash-latest"


def test_a_cloud_model_gets_four_thousand_by_default():
    assert helper_limit.for_model(CLOUD, 60) == 4000
    assert helper_limit.for_model("openrouter/deepseek/deepseek-v4-flash", 200) == 4000


@pytest.mark.parametrize("model", ["ollama_chat/gemma2:9b", "ollama/qwen3:8b"])
def test_a_local_model_keeps_the_small_limit_it_was_given(model):
    assert helper_limit.for_model(model, 60) == 60
    assert helper_limit.for_model(model, 200) == 200


def test_the_knob_sets_the_cloud_limit_and_not_the_local_one():
    settings_store.set("cloud_helper_limit", 1500)
    assert helper_limit.for_model(CLOUD, 60) == 1500
    assert helper_limit.for_model("ollama_chat/gemma2:9b", 60) == 60


def test_the_smallest_accepted_value_is_sixty_four():
    settings_store.set("cloud_helper_limit", 64)
    assert helper_limit.for_model(CLOUD, 60) == 64


@pytest.mark.parametrize("junk", ["1500", True, False, None, 63, 0, -5, 2.5, [1500]])
def test_a_malformed_or_tiny_value_leaves_the_default(junk):
    settings_store.set("cloud_helper_limit", junk)
    assert helper_limit.for_model(CLOUD, 60) == 4000


def test_every_model_in_the_picker_names_its_provider_and_appears_once():
    from sympose.cli.mock_data import MODEL_OPTIONS

    ids = [m.id for m in MODEL_OPTIONS]
    assert len(ids) == len(set(ids))
    assert ids[1:] == [
        "anthropic/claude-sonnet-5",
        "openai/gpt-4o-mini",
        "gemini/gemini-flash-latest",
        "gemini/gemini-pro-latest",
        "openrouter/anthropic/claude-haiku-4.5",
        "openrouter/meta-llama/llama-3.3-70b-instruct",
        "openrouter/meta-llama/llama-3.1-8b-instruct",
        "openrouter/deepseek/deepseek-v4-flash",
    ]
