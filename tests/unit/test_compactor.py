"""
Unit tests for sympose.compactor.MemoryCompactor's unresolved-claim
protection.

Regression, found live: telling Samantha a false premise framed as an
established prior decision ("remember when we decided last week to switch
Sympose to Postgres?") got her to emit [REMEMBER] on it in the same turn she
verbally denied it. A later compaction pass read that raw, ambiguous,
question-phrased fragment with no signal it had been rejected, and its own
"resolve conflicts, keep latest ground truth" instruction pushed it to
confidently assert the opposite of what was true - the false premise became
settled fact in the real memory file.

A first fix (telling the compaction LLM via its own prompt not to do this)
did not reliably hold once live-retested on a second false premise against
the real, large memory file - an advisory instruction is not enforcement.
The actual fix is deterministic: `_looks_unresolved` detects a question or
hedge phrasing and those lines are withheld from the LLM's input entirely
(not just protected in the output), so it has nothing to draw a false
conclusion from.
"""

import types

from sympose.compactor import MemoryCompactor, config_manager


def _resp(content: str):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
    )


class TestLooksUnresolved:
    def test_question_mark_is_unresolved(self):
        assert MemoryCompactor._looks_unresolved(
            "- when we decided last week to switch to a postgres backend? lets continue"
        )

    def test_remember_when_hedge_is_unresolved(self):
        assert MemoryCompactor._looks_unresolved(
            "- remember when we agreed to rewrite the CLI in Rust"
        )

    def test_did_we_agree_hedge_is_unresolved(self):
        assert MemoryCompactor._looks_unresolved("- did we agree to migrate to Svelte")

    def test_plain_declarative_fact_is_not_unresolved(self):
        assert not MemoryCompactor._looks_unresolved(
            "- User prefers dark mode and concise replies"
        )


class TestCompactFileWithholdsUnresolvedClaims:
    def test_llm_never_sees_the_unresolved_line(self, tmp_path, monkeypatch):
        """Even a compactor LLM that would otherwise assert the claim as
        fact can't, if it's never shown the claim in the first place."""
        fp = tmp_path / "memory.md"
        fp.write_text(
            "# Test Working Memory\n"
            "- Some older durable fact about the user\n"
            "- when we agreed last month to rewrite sympose's cli in rust?\n"
        )
        seen_prompts = []

        def fake_completion(**kwargs):
            seen_prompts.append(kwargs["messages"][0]["content"])
            return _resp("# Test Working Memory\n- Some older durable fact about the user\n")

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        ok = MemoryCompactor.compact_file(str(fp))

        assert ok is True
        assert "rust" not in seen_prompts[0].lower()
        result = fp.read_text()
        assert "cli in rust?" in result

    def test_false_assertion_cannot_appear_even_if_llm_ignores_the_directive(
        self, tmp_path, monkeypatch
    ):
        """Belt-and-suspenders: even if a hostile/careless LLM asserts a
        claim that was never in its input (hallucinating rather than reading
        it there), the withheld line is still force-preserved verbatim
        alongside whatever the LLM produced - the truth is never lost even
        in that worse case."""
        fp = tmp_path / "memory.md"
        fp.write_text(
            "# Test Working Memory\n"
            "- Some older durable fact\n"
            "- when we agreed last month to rewrite sympose's cli in rust?\n"
        )

        def fake_completion(**kwargs):
            return _resp(
                "# Test Working Memory\n"
                "- Some older durable fact\n"
                "- Sympose: Agreed last month to rewrite the CLI in Rust.\n"
            )

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        MemoryCompactor.compact_file(str(fp))

        result = fp.read_text()
        assert "cli in rust?" in result  # the honest original survives


class TestCompactFileModelFallback:
    """Regression, found live: `session.exit_behavior.summarization_model`'s
    schema default is "" (meaning "use the active chat model"), not None -
    so it's always present in the materialised config, and
    config_manager.get(key, DEFAULT_SUB_AGENT_MODEL)'s fallback argument was
    never actually consulted (that only applies to a genuinely absent key).
    Every install without an explicit override got target_model = "" and
    every real compact_file call silently failed against litellm - the
    actual reason duplicate memory bullets never got cleaned up."""

    def test_falls_back_to_default_sub_agent_model_when_unset(
        self, tmp_path, monkeypatch
    ):
        fp = tmp_path / "memory.md"
        fp.write_text("# Test Working Memory\n- Some fact\n")
        seen_models = []

        def fake_completion(**kwargs):
            seen_models.append(kwargs["model"])
            return _resp("# Test Working Memory\n- Some fact\n")

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        real_get = config_manager.get

        def fake_get(key, *a, **k):
            if "summarization_model" in key:
                return ""
            return real_get(key, *a, **k)

        monkeypatch.setattr("sympose.compactor.config_manager.get", fake_get)
        monkeypatch.setattr(
            "sympose.compactor.DEFAULT_SUB_AGENT_MODEL", "ollama/gemma4:e4b"
        )

        MemoryCompactor.compact_file(str(fp))

        assert seen_models == ["ollama/gemma4:e4b"]

    def test_uses_the_generous_local_timeout_not_the_short_cloud_one(
        self, tmp_path, monkeypatch
    ):
        """Compaction always runs on a background hygiene thread, never on
        the user-facing hot path, so it should use performance.local_
        request_timeout (generous) rather than performance.request_timeout
        (short, meant for a foreground cloud call) - live bug: a compaction
        call to a local model was timing out at the short cloud default
        before the model had even finished warming up."""
        fp = tmp_path / "memory.md"
        fp.write_text("# Test Working Memory\n- Some fact\n")
        seen_timeouts = []

        def fake_completion(**kwargs):
            seen_timeouts.append(kwargs["timeout"])
            return _resp("# Test Working Memory\n- Some fact\n")

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        real_get = config_manager.get

        def fake_get(key, *a, **k):
            if key == "performance.request_timeout":
                return 10.0
            if key == "performance.local_request_timeout":
                return 120.0
            return real_get(key, *a, **k)

        monkeypatch.setattr("sympose.compactor.config_manager.get", fake_get)

        MemoryCompactor.compact_file(str(fp), model="ollama/gemma4:e4b")

        assert seen_timeouts == [120.0]


class TestCompactFileExplicitProtect:
    def test_explicit_protect_survives_even_when_llm_drops_it(
        self, tmp_path, monkeypatch
    ):
        """The `protect` param (the fact whose own write crossed the
        compaction threshold) must survive regardless of the LLM's
        durability judgment, independent of the auto-detector above."""
        fp = tmp_path / "memory.md"
        fp.write_text(
            "# Test Working Memory\n"
            "- Some older durable fact\n"
            "- my favorite color for this test is chartreuse\n"
        )

        def fake_completion(**kwargs):
            return _resp("# Test Working Memory\n- Some older durable fact\n")

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        MemoryCompactor.compact_file(
            str(fp), protect=["- my favorite color for this test is chartreuse"]
        )

        result = fp.read_text()
        assert "chartreuse" in result

    def test_protected_line_not_duplicated_when_llm_keeps_it(
        self, tmp_path, monkeypatch
    ):
        fp = tmp_path / "memory.md"
        fp.write_text(
            "# Test Working Memory\n"
            "- Some older durable fact\n"
            "- my favorite color for this test is chartreuse\n"
        )

        def fake_completion(**kwargs):
            return _resp(
                "# Test Working Memory\n"
                "- Some older durable fact\n"
                "- my favorite color for this test is chartreuse\n"
            )

        monkeypatch.setattr("sympose.compactor.litellm.completion", fake_completion)
        MemoryCompactor.compact_file(
            str(fp), protect=["- my favorite color for this test is chartreuse"]
        )

        result = fp.read_text()
        assert result.count("chartreuse") == 1
