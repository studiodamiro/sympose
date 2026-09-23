"""Tests for sympose.engine.budget (docs/decisions/015): which window a turn
gets, and how a prompt is fitted to it. Token counts here are plain word
counts so every expectation can be worked out by hand."""

import pytest

from sympose import settings_store
from sympose.engine import budget
from sympose.engine.model import EngineModelError


_REAL_COUNT_TOKENS = budget.count_tokens  # captured before the fixture replaces it


def words(n: int) -> str:
    return " ".join(["w"] * n)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(budget, "_NATIVE_MAX", {})
    monkeypatch.setattr(
        budget, "count_tokens", lambda messages, model: sum(len(m["content"].split()) for m in messages)
    )


def native(monkeypatch, sizes: dict[str, int]):
    """Stands in for litellm's model info: the listed models have a maximum
    window, any other raises like an unknown model or a local server that is
    not up."""

    def info(model):
        if model not in sizes:
            raise KeyError(model)
        return {"max_input_tokens": sizes[model]}

    monkeypatch.setattr(budget.litellm, "get_model_info", info)


# -- which window a turn gets ---------------------------------------------


def test_with_no_setting_a_local_model_follows_its_own_maximum(monkeypatch):
    native(monkeypatch, {"ollama_chat/small": 4096, "ollama_chat/mid": 8192, "ollama_chat/big": 32768})
    assert budget.window_for("ollama_chat/small") == 4096
    assert budget.window_for("ollama_chat/mid") == 8192
    assert budget.window_for("ollama_chat/big") == 32768


def test_switching_model_changes_the_window_automatically(monkeypatch):
    native(monkeypatch, {"ollama_chat/small": 4096, "ollama_chat/big": 32768})
    assert budget.window_for("ollama_chat/small") != budget.window_for("ollama_chat/big")


def test_a_huge_model_maximum_is_capped_unless_the_user_asks_for_more(monkeypatch):
    native(monkeypatch, {"ollama_chat/huge": 131072})
    assert budget.window_for("ollama_chat/huge") == 32768  # the automatic ceiling
    settings_store.set("context_window", 65536)
    assert budget.window_for("ollama_chat/huge") == 65536  # a deliberate choice is honoured


def test_a_users_setting_caps_every_model_and_is_kept_when_the_model_changes(monkeypatch):
    native(monkeypatch, {"ollama_chat/small": 4096, "ollama_chat/big": 32768})
    settings_store.set("context_window", 2048)
    assert budget.window_for("ollama_chat/small") == 2048
    assert budget.window_for("ollama_chat/big") == 2048
    settings_store.set("context_window", 16384)
    assert budget.window_for("ollama_chat/big") == 16384
    assert budget.window_for("ollama_chat/small") == 4096  # never past what the model supports


def test_a_model_whose_maximum_is_unknown_gets_ollamas_own_default_unless_the_user_chose(monkeypatch):
    native(monkeypatch, {})
    assert budget.window_for("ollama_chat/whatever") == 4096
    settings_store.set("context_window", 6000)
    assert budget.window_for("ollama_chat/whatever") == 6000


@pytest.mark.parametrize("junk", ["8192", True, False, None, 12.5, [4096], 0, -5])
def test_a_malformed_setting_means_automatic(monkeypatch, junk):
    native(monkeypatch, {"ollama_chat/m": 8192})
    settings_store.set("context_window", junk)
    assert budget.context_setting() is None
    assert budget.window_for("ollama_chat/m") == 8192


@pytest.mark.parametrize("small", [1, 500, 1023])
def test_a_small_setting_is_raised_to_the_smallest_usable_window_not_read_as_automatic(monkeypatch, small):
    """Someone asking for a tiny window wants a small footprint: treating it as
    automatic would give them the opposite (the model's whole maximum)."""
    native(monkeypatch, {"ollama_chat/m": 32768})
    settings_store.set("context_window", small)
    assert budget.context_setting() == 1024
    assert budget.window_for("ollama_chat/m") == 1024


def test_a_usable_setting_is_used(monkeypatch):
    settings_store.set("context_window", 1024)
    assert budget.context_setting() == 1024


def test_a_cloud_model_gets_the_providers_window_and_ignores_the_setting(monkeypatch):
    native(monkeypatch, {"gpt-x": 128000})
    settings_store.set("context_window", 2048)
    assert budget.window_for("gpt-x") == 128000
    assert budget.window_for("unknown-cloud-model") is None
    assert budget.budget_for("unknown-cloud-model") is None


def test_the_local_budget_reserves_room_for_the_reply_and_caps_it(monkeypatch):
    native(monkeypatch, {"ollama_chat/m": 8192})
    assert budget.budget_for("ollama_chat/m") == budget.Budget(
        prompt_tokens=6144, num_ctx=8192, reply_cap=2048  # a quarter of the window
    )
    settings_store.set("context_window", 2048)
    assert budget.budget_for("ollama_chat/m") == budget.Budget(
        prompt_tokens=1536, num_ctx=2048, reply_cap=512
    )


def test_the_reply_room_grows_with_the_window_up_to_a_ceiling(monkeypatch):
    native(monkeypatch, {"ollama_chat/big": 32768, "ollama_chat/huge": 131072})
    assert budget.budget_for("ollama_chat/big").reply_cap == 4096  # not 8192
    assert budget.budget_for("ollama_chat/huge").reply_cap == 4096  # capped window, same ceiling


def test_a_users_reply_limit_is_used_but_never_more_than_half_the_window(monkeypatch):
    native(monkeypatch, {"ollama_chat/m": 8192})
    settings_store.set("reply_limit", 300)
    assert budget.budget_for("ollama_chat/m").reply_cap == 300
    assert budget.budget_for("ollama_chat/m").prompt_tokens == 8192 - 300
    settings_store.set("reply_limit", 100000)
    assert budget.budget_for("ollama_chat/m").reply_cap == 4096  # half of 8192


@pytest.mark.parametrize("junk", ["500", True, None, 63, 0, -1, 2.5])
def test_a_malformed_or_tiny_reply_limit_means_automatic(monkeypatch, junk):
    native(monkeypatch, {"ollama_chat/m": 8192})
    settings_store.set("reply_limit", junk)
    assert budget.budget_for("ollama_chat/m").reply_cap == 2048


def test_the_cloud_budget_sends_no_window_and_no_reply_cap_but_keeps_room_for_the_reply(monkeypatch):
    native(monkeypatch, {"gpt-x": 128000, "gpt-small": 8192})
    assert budget.budget_for("gpt-x") == budget.Budget(
        prompt_tokens=128000 - 4096, num_ctx=None, reply_cap=None
    )
    # Some providers share one window between input and output.
    assert budget.budget_for("gpt-small").prompt_tokens == 8192 - 2048


def test_a_models_maximum_is_looked_up_once(monkeypatch):
    calls = []

    def info(model):
        calls.append(model)
        return {"max_input_tokens": 4096}

    monkeypatch.setattr(budget.litellm, "get_model_info", info)
    budget.window_for("ollama_chat/m")
    budget.window_for("ollama_chat/m")
    assert calls == ["ollama_chat/m"]


def test_a_failed_lookup_is_asked_again_next_time(monkeypatch):
    native(monkeypatch, {})
    assert budget.window_for("ollama_chat/m") == 4096  # server down: Ollama's own default
    native(monkeypatch, {"ollama_chat/m": 8192})  # ...and now it is up
    assert budget.window_for("ollama_chat/m") == 8192


# -- counting ---------------------------------------------------------------


def test_the_engines_own_count_carries_a_safety_margin(monkeypatch):
    monkeypatch.undo()  # the real `count_tokens`, not this file's word counter
    monkeypatch.setattr(budget, "_count_raw", lambda messages, model: 100)
    assert budget.count_tokens([], "m") == 115
    monkeypatch.setattr(budget, "_count_raw", lambda messages, model: 3)
    assert budget.count_tokens([], "m") == 4  # rounded up, never down


def test_a_failing_token_counter_degrades_to_an_estimate_not_an_error(monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("no tokenizer")

    monkeypatch.setattr(budget.litellm, "token_counter", broken)
    # One token per character at worst, so dense text (CJK) is never under-counted.
    assert budget._count_raw([{"role": "user", "content": "あ" * 300}], "m") >= 300


# -- fitting ------------------------------------------------------------------


def builder(system_words: int, user_words: int):
    """A prompt of a system message (`system_words`, plus 10 words per
    passage), the history, and the new message."""

    def build(history, hits):
        system = words(system_words) + "".join(" " + words(10) for _ in hits)
        return [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": words(user_words)},
        ]

    return build


def turns(n: int, per_message: int = 10):
    history = []
    for i in range(n):
        history += [
            {"role": "user", "content": f"t{i} " + words(per_message - 1)},
            {"role": "assistant", "content": f"t{i} " + words(per_message - 1)},
        ]
    return history


def test_everything_that_fits_is_kept():
    hits = [{"id": 1}, {"id": 2}]
    fitted = budget.fit(builder(20, 5), turns(2), hits, "m", prompt_tokens=200)
    assert fitted.history_dropped == 0 and fitted.grounding == hits
    assert len(fitted.messages) == 1 + 4 + 1


def test_the_oldest_turns_are_dropped_first_and_only_as_many_as_needed():
    hits = [{"id": 1}]
    # system 20 + one passage 10 + new message 5 = 35; each turn is 20.
    fitted = budget.fit(builder(20, 5), turns(4), hits, "m", prompt_tokens=35 + 40)
    assert fitted.history_dropped == 2
    kept = [m["content"].split()[0] for m in fitted.messages[1:-1]]
    assert kept == ["t2", "t2", "t3", "t3"]
    assert fitted.grounding == hits  # the passages survive while history can still give way


def test_a_turn_is_never_split_in_half():
    # Room for two and a half turns keeps two, and history still starts with the user.
    fitted = budget.fit(builder(20, 5), turns(4), [], "m", prompt_tokens=25 + 50)
    assert fitted.history_dropped == 2
    assert [m["role"] for m in fitted.messages[1:-1]] == ["user", "assistant", "user", "assistant"]


def test_the_system_prompt_and_the_new_message_survive_dropping_all_history():
    fitted = budget.fit(builder(20, 5), turns(6), [], "m", prompt_tokens=25)
    assert fitted.history_dropped == 6
    assert len(fitted.messages) == 2
    assert fitted.messages[0]["role"] == "system" and len(fitted.messages[0]["content"].split()) == 20
    assert fitted.messages[-1]["role"] == "user" and len(fitted.messages[-1]["content"].split()) == 5


def test_passages_go_only_after_history_and_the_lowest_scoring_first():
    hits = [{"id": 1}, {"id": 2}, {"id": 3}]  # best first, 10 words each
    # fixed 25 + three passages 30 + one turn 20 = 75; room for 45.
    fitted = budget.fit(builder(20, 5), turns(1), hits, "m", prompt_tokens=45)
    assert fitted.history_dropped == 1
    assert fitted.grounding == [{"id": 1}, {"id": 2}]


def test_when_the_fixed_part_alone_does_not_fit_it_fails_loudly_instead_of_cutting_it():
    with pytest.raises(budget.ContextTooSmallError) as error:
        budget.fit(builder(100, 5), turns(3), [{"id": 1}], "m", prompt_tokens=50)
    assert "context_window" in str(error.value)
    assert isinstance(error.value, EngineModelError)


def test_the_inputs_are_not_modified():
    history, hits = turns(4), [{"id": 1}, {"id": 2}]
    budget.fit(builder(20, 5), history, hits, "m", prompt_tokens=30)
    assert len(history) == 8 and len(hits) == 2


def test_a_prompt_exactly_at_the_limit_fits_and_one_over_does_not():
    build = builder(20, 5)  # 25 words fixed; each turn adds 20
    at_limit = budget.fit(build, turns(1), [], "m", prompt_tokens=45)
    assert at_limit.history_dropped == 0
    one_over = budget.fit(build, turns(1), [], "m", prompt_tokens=44)
    assert one_over.history_dropped == 1


def test_fit_applies_the_safety_margin(monkeypatch):
    monkeypatch.setattr(budget, "count_tokens", _REAL_COUNT_TOKENS)  # the margin is in the real one
    monkeypatch.setattr(budget, "_count_raw", lambda messages, model: sum(len(m["content"].split()) for m in messages))
    build = builder(20, 5)  # 45 words with one turn: 45 * 1.15 = 52 (rounded up)
    assert budget.fit(build, turns(1), [], "m", prompt_tokens=52).history_dropped == 0
    assert budget.fit(build, turns(1), [], "m", prompt_tokens=51).history_dropped == 1


def test_the_too_small_error_tells_the_user_to_shorten_a_very_long_message_too():
    with pytest.raises(budget.ContextTooSmallError, match="shorten it"):
        budget.fit(builder(10, 500), [], [], "m", prompt_tokens=100)


# -- the real litellm result shape (no fakes, no network) ------------------


def test_real_litellm_model_info_gives_windows_in_the_shape_the_budget_reads():
    """The other tests fake `get_model_info`; this pins the real one, so a
    change in what litellm returns cannot silently drop every model to the
    unknown-window path."""
    local = budget.window_for("ollama/llama3")  # a model litellm knows statically
    assert isinstance(local, int) and 1024 <= local <= budget.AUTO_WINDOW_CEILING
    cloud = budget.window_for("gpt-4o")
    assert isinstance(cloud, int) and cloud > 8192
    assert budget.budget_for("gpt-4o").num_ctx is None
