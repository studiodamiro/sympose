"""
Unit tests for sympose.engine.PersonaEngine — the litellm call kwargs assembler
(local-backend `keep_alive` residency passthrough) and `_visible_stream`, the
gate that stops user-visible output at the first autonomic retrieval tag.
"""

import types

import pytest

from sympose.engine import PersonaEngine
from sympose.profiles import ProfileManager


@pytest.fixture
def engine(tmp_path):
    return PersonaEngine(ProfileManager(profiles_dir=str(tmp_path)))


def _chunks(*parts):
    """Fake a litellm streaming response from text pieces."""
    for p in parts:
        yield types.SimpleNamespace(
            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=p))]
        )


class TestVisibleStreamGate:
    def _run(self, engine, *parts):
        sink = []
        out = "".join(engine._visible_stream(_chunks(*parts), sink))
        return out, sink[0]

    def test_plain_text_passes_through(self, engine):
        out, raw = self._run(engine, "Here is ", "the whole ", "answer.")
        assert out == "Here is the whole answer."
        assert raw == "Here is the whole answer."

    def test_cuts_at_spawn_sub_agent_tag(self, engine):
        out, raw = self._run(
            engine,
            "Let me check the vault. ",
            "[SPAWN_SUB_AGENT: vault_read | Dylan] ",
            "Here is Dylan's note: Created 2021-06-15, a close friend...",
        )
        assert out == "Let me check the vault. "
        assert "close friend" not in out
        # the raw text still carries the tag for ActionProcessor
        assert "[SPAWN_SUB_AGENT: vault_read | Dylan]" in raw

    def test_cuts_at_search_tag_split_across_chunks(self, engine):
        out, raw = self._run(
            engine, "One sec ", "[SEA", "RCH: btc price] ", "It is $70k"
        )
        assert out == "One sec "
        assert "70k" not in out

    def test_tag_only_reply_yields_nothing_visible(self, engine):
        out, raw = self._run(engine, "[SPAWN_SUB_AGENT: vault_read | grief]")
        assert out == ""
        assert raw == "[SPAWN_SUB_AGENT: vault_read | grief]"

    def test_cuts_at_write_note_tag(self, engine):
        """Regression: only the 3 retrieval tags were ever gated - every other
        tag (WRITE_NOTE, REMEMBER, DAILY_NOTE, ...) just sat in the holdback
        buffer and got unconditionally flushed once the stream ended, so its
        raw `[WRITE_NOTE: ...]` bracket syntax always leaked into the visible
        reply next to the clean confirmation badge for the same action."""
        out, raw = self._run(
            engine,
            "I've created the note for you in your Thoughts folder.\n\n",
            "[WRITE_NOTE: Thoughts/Test.md | This is a test note.]",
        )
        assert out == "I've created the note for you in your Thoughts folder.\n\n"
        assert "WRITE_NOTE" not in out
        assert "[WRITE_NOTE: Thoughts/Test.md | This is a test note.]" in raw

    def test_cuts_at_remember_tag(self, engine):
        out, raw = self._run(
            engine,
            "Got it logged into working memory for you.\n\n",
            "[REMEMBER: Second test fact is a lavender bicycle]",
        )
        assert out == "Got it logged into working memory for you.\n\n"
        assert "REMEMBER" not in out


class TestIsFullBodyVaultCtx:
    """Live bug: a persona was handed a thin search-results digest (titles +
    one-line snippets, no full text) as pre-turn vault_ctx, and chat_stream's
    `strict = ... and not vault_ctx` treated any non-empty vault_ctx as
    "real grounding" and disabled the fabrication check entirely for the
    turn - the model then invented a whole essay to fill the gap between a
    one-line snippet and an actual conversation. Only a full verbatim note
    body (marked "Exact Content" everywhere vault.py returns one) is strong
    enough grounding to justify that."""

    def test_none_and_empty_are_not_full_body(self, engine):
        assert engine._is_full_body_vault_ctx(None) is False
        assert engine._is_full_body_vault_ctx("") is False

    def test_search_digest_is_not_full_body(self, engine):
        assert not engine._is_full_body_vault_ctx(
            "### Ground-Truth Vault Search Results for 'thoughts':\n"
            "**[1] `Thoughts/A.md`** *(Title Match)*\n  > some snippet"
        )

    def test_backlink_digest_is_not_full_body(self, engine):
        assert not engine._is_full_body_vault_ctx(
            "### Ground-Truth Vault Backlink Index for `[[Dylan]]`:\n- People/Tin.md"
        )

    def test_exact_content_note_is_full_body(self, engine):
        assert engine._is_full_body_vault_ctx(
            "### Ground-Truth Sandboxed Vault Note (`People/Dylan.md` - Exact "
            "Content):\n# Dylan\n\nson, born 2015-09-08."
        )

    def test_random_sample_note_is_full_body(self, engine):
        assert engine._is_full_body_vault_ctx(
            "### Ground-Truth Selected Note from `Thoughts/` (Exact Content):\n"
            "### Ground-Truth Sandboxed Vault Note (`Thoughts/A.md` — Exact "
            "Content, matched 'thoughts'):\nSome thoughts here."
        )


class TestVaultCtxCitationMismatch:
    """Live bug: even handed a real, correctly-retrieved note body, a local
    model invented a *different*, fictional note (a plausible-looking but
    nonexistent path) instead of quoting the one it was actually given —
    "Exact Content" being present doesn't mean the model used it. This check
    catches a reply naming a note path that never appears anywhere in the
    ground-truth it was handed, so `chat_stream` can swap the invented
    answer for the real one rather than trust it."""

    def test_reply_citing_a_different_path_is_a_mismatch(self, engine):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Daily/2023-05-17.md` "
            "- Exact Content):\n# Day\n\nStudy more react.\n"
        )
        reply = "**Retrieved Note: `Thoughts/hmmm.md`**\n\nSome invented text."
        assert engine._vault_ctx_citation_mismatch(reply, vault_ctx)

    def test_reply_quoting_the_real_path_is_not_a_mismatch(self, engine):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Thoughts/A.md` "
            "- Exact Content):\n# Thoughts\n\nOn entropy.\n"
        )
        reply = "From `Thoughts/A.md`:\n\n# Thoughts\n\nOn entropy."
        assert not engine._vault_ctx_citation_mismatch(reply, vault_ctx)

    def test_reply_naming_no_path_at_all_is_not_flagged(self, engine):
        # No structural signal to check against - can't be verified without
        # a second model call, which stays a known residual gap rather than
        # something forced through a false-positive block.
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Thoughts/A.md` "
            "- Exact Content):\n# Thoughts\n\nOn entropy.\n"
        )
        reply = "You wrote a nice reflection on entropy and joy."
        assert not engine._vault_ctx_citation_mismatch(reply, vault_ctx)

    def test_no_vault_ctx_is_never_a_mismatch(self, engine):
        assert not engine._vault_ctx_citation_mismatch("Some/Made.md up path", None)

    def test_strip_vault_ctx_headers_leaves_only_the_body(self, engine):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Thoughts/A.md` "
            "- Exact Content):\n# Thoughts\n\nOn entropy.\n"
        )
        assert engine._strip_vault_ctx_headers(vault_ctx) == "# Thoughts\n\nOn entropy."


class TestVaultCtxTitleMissing:
    """Live bug, confirmed by repeated live runs: handed a real note -
    regardless of topic - gemma4:e4b narrated a specific, unrelated,
    sometimes nonexistent title in prose instead of referencing what it
    actually had, every time. `_vault_ctx_citation_mismatch` doesn't catch
    this since the fabricated reply names no path at all; this sibling
    check catches the same failure from the other side: the real note's
    own title never showing up anywhere in the reply."""

    def test_real_note_title_never_mentioned_is_flagged(self, engine):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Movies/Monster.md` "
            "- Exact Content):\n# Monster\n\nA true-crime character study.\n"
        )
        reply = "The random note pulled is about *Arrival*. The film explores..."
        assert engine._vault_ctx_title_missing(reply, vault_ctx)

    def test_real_note_title_mentioned_is_not_flagged(self, engine):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Movies/Monster.md` "
            "- Exact Content):\n# Monster\n\nA true-crime character study.\n"
        )
        reply = "The note pulled is about *Monster* - a true-crime character study."
        assert not engine._vault_ctx_title_missing(reply, vault_ctx)

    def test_short_generic_stem_is_not_flagged(self, engine):
        """A stem under 4 characters (e.g. a single-letter or terse note
        name) is skipped - too likely to coincidentally appear (or not)
        in ordinary prose to be a reliable signal either way. Known,
        accepted trade-off: a genuinely short real title like "Her" is
        skipped by the same rule and this check simply never fires for it,
        rather than risk being noisy on short/common words in general."""
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Thoughts/A.md` "
            "- Exact Content):\n# Thoughts\n\nOn entropy.\n"
        )
        reply = "You wrote a nice reflection on entropy and joy."
        assert not engine._vault_ctx_title_missing(reply, vault_ctx)

    def test_no_vault_ctx_is_never_flagged(self, engine):
        assert not engine._vault_ctx_title_missing("Anything at all.", None)

    def test_at_least_one_of_several_sampled_notes_mentioned_is_enough(
        self, engine
    ):
        vault_ctx = (
            "### Ground-Truth Sandboxed Vault Note (`Movies/Monster.md` "
            "- Exact Content):\nAbout Monster.\n\n---\n\n"
            "### Ground-Truth Sandboxed Vault Note (`Movies/Limitless.md` "
            "- Exact Content):\nAbout Limitless.\n"
        )
        reply = "One of the pulled notes was about *Limitless* and a smart drug."
        assert not engine._vault_ctx_title_missing(reply, vault_ctx)


class TestGroundingModeKnob:
    """`vault_grounding: auto` derives strict/trust from the model: a local
    backend (or localhost api_base) → strict, cloud → trust. An explicit
    `strict`/`trust` on the persona wins."""

    def test_local_ollama_model_is_strict_under_auto(self, engine):
        assert engine._grounding_mode({}, "ollama_chat/qwen2.5:14b") == "strict"
        assert engine._grounding_mode({}, "ollama/llama3.1:8b") == "strict"

    def test_cloud_model_is_trust_under_auto(self, engine):
        assert engine._grounding_mode({}, "gemini/gemini-3.6-flash") == "trust"
        assert engine._grounding_mode({}, "openrouter/x/y") == "trust"

    def test_localhost_api_base_forces_strict(self, engine):
        assert (
            engine._grounding_mode(
                {"api_base": "http://localhost:11434"}, "openai/gpt-x"
            )
            == "strict"
        )

    def test_explicit_persona_setting_wins(self, engine):
        assert (
            engine._grounding_mode({"vault_grounding": "trust"}, "ollama/llama3")
            == "trust"
        )
        assert (
            engine._grounding_mode({"vault_grounding": "strict"}, "gemini/flash")
            == "strict"
        )

    def test_global_default_overrides_auto(self, engine):
        engine.config.set("vault.grounding_default", "strict")
        try:
            assert engine._grounding_mode({}, "gemini/gemini-3.6-flash") == "strict"
        finally:
            engine.config.set("vault.grounding_default", None)


class TestVaultClaimRegex:
    """Regression, found live: a local model given a manual /model override
    (which intentionally bypasses routing but still expects strict grounding
    to catch fabrication) invented an entire fake "Sub-Agent Report" block
    with placeholder movie names, then recapped it as "These are the movies
    you've given a perfect rating in your vault." — a real vault-grounding
    claim. `_VAULT_CLAIM_RE`'s `in your vault[,\\s]` alternative required a
    comma or whitespace immediately after "vault", so a claim ending the
    sentence with a period (the common case) was never recognized, and the
    strict-mode fabrication catch it feeds never fired."""

    def test_claim_ending_in_a_period_is_caught(self, engine):
        assert engine._VAULT_CLAIM_RE.search(
            "These are the movies you've given a perfect rating in your vault."
        )

    def test_claim_ending_in_other_punctuation_is_caught(self, engine):
        assert engine._VAULT_CLAIM_RE.search("I found that note in your vault!")
        assert engine._VAULT_CLAIM_RE.search("Did I mention that in your vault?")

    def test_claim_mid_sentence_still_caught(self, engine):
        assert engine._VAULT_CLAIM_RE.search("in your vault, there are many notes")

    def test_fabricated_note_path_citation_is_caught(self, engine):
        """Live failure: asked "ever heard of random note pull?", a local
        model invented a "Wild Card Note Pull" card citing a fake source path
        ("**Source:** `General/Personal Philosophy.md`") and a full invented
        passage, with no `[SPAWN_SUB_AGENT: ...]` tag anywhere in the reply -
        so no wording in the old alternatives ("in your vault", "your note",
        ...) ever appeared and the fabrication streamed straight through."""
        assert engine._VAULT_CLAIM_RE.search(
            "**Source:** `General/Personal Philosophy.md` (A canvas you "
            "created six months ago)"
        )
        assert engine._VAULT_CLAIM_RE.search("Source: People/Dylan.md")

    def test_unrelated_dotted_path_not_mistaken_for_a_note(self, engine):
        """The path alternative is scoped to `.md` specifically so ordinary
        talk about code files (a `.py`/`.json` path with no bearing on the
        vault) doesn't trip the same fabrication catch."""
        assert not engine._VAULT_CLAIM_RE.search("check src/app.py for that")


class TestResolveKeepAlive:
    """keep_alive is a property of which model is loaded into Ollama, not
    which persona calls it. `performance.local_model_keep_alive` (keyed by
    exact model id) is the one source of truth once two personas share a
    model; a persona's own `keep_alive` and the global
    `performance.local_keep_alive` are progressively broader fallbacks.

    `engine.config` is the process-wide singleton (this machine's real
    config.yaml, not a fixture-scoped copy), so every test here snapshots
    and restores the two keys it touches rather than assuming a blank slate."""

    @pytest.fixture(autouse=True)
    def _isolate_config(self, engine):
        orig_global = engine.config.get("performance.local_keep_alive")
        orig_per_model = engine.config.get("performance.local_model_keep_alive")
        yield
        engine.config.set("performance.local_keep_alive", orig_global)
        engine.config.set("performance.local_model_keep_alive", orig_per_model)

    def test_no_config_defers_to_none(self, engine):
        engine.config.set("performance.local_keep_alive", None)
        engine.config.set("performance.local_model_keep_alive", {})
        assert engine._resolve_keep_alive({}, "ollama/llama3.1:8b") is None

    def test_global_fallback_applies_to_any_local_model(self, engine):
        engine.config.set("performance.local_keep_alive", "30m")
        assert engine._resolve_keep_alive({}, "ollama/llama3.1:8b") == "30m"

    def test_persona_keep_alive_wins_over_global(self, engine):
        engine.config.set("performance.local_keep_alive", "30m")
        assert (
            engine._resolve_keep_alive({"keep_alive": -1}, "ollama/llama3.1:8b")
            == -1
        )

    def test_per_model_entry_wins_over_persona_and_global(self, engine):
        engine.config.set("performance.local_keep_alive", "30m")
        engine.config.set(
            "performance.local_model_keep_alive", {"ollama/llama3.1:8b": 0}
        )
        assert (
            engine._resolve_keep_alive({"keep_alive": -1}, "ollama/llama3.1:8b")
            == 0
        )

    def test_per_model_entry_for_a_different_model_does_not_apply(self, engine):
        engine.config.set(
            "performance.local_model_keep_alive", {"ollama/other:1b": 0}
        )
        assert (
            engine._resolve_keep_alive({"keep_alive": -1}, "ollama/llama3.1:8b")
            == -1
        )


class TestEntityGuess:
    def test_pull_x_entry(self, engine):
        assert (
            engine._entity_guess("Certainly, I can pull Dylan's entry from your vault.")
            == "Dylan"
        )

    def test_do_you_know_x(self, engine):
        assert engine._entity_guess("do you know dylan?").lower() == "dylan"

    def test_falls_through_to_capitalised_name(self, engine):
        assert (
            engine._entity_guess("what did I say about Marguerite last year")
            == "Marguerite"
        )

    def test_nothing_when_no_subject(self, engine):
        assert engine._entity_guess("yes, just summarize", "sure go ahead") == ""

    def test_extra_stop_suppresses_a_dynamic_name(self, engine):
        """The active user's and personas' own names are resolved per
        install (chat_stream builds this set from ProfileManager, not a
        fixed list) - any name can be excluded this way, not just one
        install's own. Regression: this used to be a hardcoded class-level
        set of one user's actual persona names, which would never have
        worked for a different install's own names."""
        assert (
            engine._entity_guess(
                "what did I say about Grace last year", extra_stop={"grace"}
            )
            == ""
        )

    def test_a_name_not_in_extra_stop_is_unaffected(self, engine):
        """Same message, same mechanism - a name only gets suppressed when
        the caller actually passes it, proving this isn't tied to any
        specific literal name in the code itself."""
        assert (
            engine._entity_guess(
                "what did I say about Grace last year", extra_stop={"dylan"}
            )
            == "Grace"
        )

    def test_ignores_sentence_initial_capitalisation(self, engine):
        """Regression: the tier-2 fallback accepted *any* capitalised word,
        including one that's only capitalised because it starts a sentence
        (or a contraction like "I'll"). Live failure: a persona's own prior
        greeting "Hello! Yes, I'm here. What can I help you with today?"
        got searched as if "Hello" were a vault-recall subject, dispatching
        a real sub-agent to search the vault for the word "Hello"."""
        assert (
            engine._entity_guess(
                "Hello! Yes, I'm here. What can I help you with today?"
            )
            == ""
        )

    def test_ignores_contraction_right_after_sentence_boundary(self, engine):
        """Second live failure with the same root cause, different text:
        "Sure, let's play! I'll pull a note from your vault..." handed back
        "I'll" as the guessed subject."""
        assert (
            engine._entity_guess(
                "Sure, let's play! I'll pull a note from your vault to get us started."
            )
            == ""
        )

    def test_still_finds_a_real_entity_mid_sentence(self, engine):
        """The fix must not blind the fallback entirely - a genuine name
        appearing mid-sentence (not sentence-initial) is still a real signal."""
        assert (
            engine._entity_guess(
                "Sure, here's a summary of what you wrote about Dylan last week."
            )
            == "Dylan"
        )


class TestBuildKwargsKeepAlive:
    def test_persona_keep_alive_passed_for_local_model(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {"keep_alive": -1}, [])
        assert kw["keep_alive"] == -1

    def test_persona_keep_alive_string_duration(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {"keep_alive": "30m"}, [])
        assert kw["keep_alive"] == "30m"

    def test_keep_alive_never_sent_for_remote_model(self, engine):
        kw = engine._build_kwargs("gemini/gemini-3.6-flash", {"keep_alive": -1}, [])
        assert "keep_alive" not in kw

    def test_absent_when_unset(self, engine):
        prior = engine.config.get("performance.local_keep_alive")
        engine.config.set("performance.local_keep_alive", None)
        try:
            kw = engine._build_kwargs("ollama/llama3", {}, [])
            assert "keep_alive" not in kw
        finally:
            engine.config.set("performance.local_keep_alive", prior)

    def test_config_default_applies_when_persona_silent(self, engine):
        engine.config.set("performance.local_keep_alive", -1)
        try:
            kw = engine._build_kwargs("ollama/llama3", {}, [])
            assert kw["keep_alive"] == -1
        finally:
            engine.config.set("performance.local_keep_alive", None)

    def test_persona_overrides_config_default(self, engine):
        engine.config.set("performance.local_keep_alive", "10m")
        try:
            kw = engine._build_kwargs("ollama/llama3", {"keep_alive": 0}, [])
            assert kw["keep_alive"] == 0
        finally:
            engine.config.set("performance.local_keep_alive", None)


class TestBuildKwargsLocalRunawayStop:
    """A broken local chat-template (no stop tokens of its own) lets
    generation run past the reply into a hallucinated `### User:` /
    `### Assistant:` continuation - seen live on a community Ollama
    fine-tune. `_build_kwargs` sets a model-agnostic `stop` list for local
    backends to cut that regardless of the model's own template. Verified
    live tonight (a real Ollama exchange that stayed clean), but that
    verification never had a permanent regression test until now.

    Writing that test caught a second, real bug: `_build_kwargs`'s own
    local-backend check only recognized a literal `ollama/` prefix, so
    `ollama_chat/...`, `lm_studio/...`, and the rest of `_grounding_mode`'s
    already-established `_LOCAL_MODEL_PREFIXES` list silently got neither
    the stop list nor keep_alive - the two "is this local" checks in the
    same file had drifted apart. Unified onto the one prefix list."""

    def test_stop_list_set_for_local_model(self, engine):
        kw = engine._build_kwargs("ollama/llama3", {}, [])
        assert kw["stop"] == list(engine._LOCAL_RUNAWAY_STOP_SEQUENCES)

    def test_stop_list_not_sent_for_cloud_model(self, engine):
        kw = engine._build_kwargs("gemini/gemini-3.6-flash", {}, [])
        assert "stop" not in kw

    def test_stop_list_set_regardless_of_keep_alive(self, engine):
        kw = engine._build_kwargs("ollama_chat/qwen2.5:14b", {"keep_alive": -1}, [])
        assert kw["stop"] == list(engine._LOCAL_RUNAWAY_STOP_SEQUENCES)

    def test_other_local_backend_prefixes_also_get_the_stop_list(self, engine):
        for backend in ("lm_studio/model", "llamafile/model", "llama-cpp-python/model"):
            kw = engine._build_kwargs(backend, {}, [])
            assert kw["stop"] == list(engine._LOCAL_RUNAWAY_STOP_SEQUENCES), backend

    def test_localhost_api_base_gets_the_stop_list_too(self, engine):
        kw = engine._build_kwargs(
            "openai/local-model", {"api_base": "http://127.0.0.1:8080"}, []
        )
        assert kw["stop"] == list(engine._LOCAL_RUNAWAY_STOP_SEQUENCES)


class TestSelectTurnModel:
    """ADR-122: engine._select_turn_model, the guard that decides whether a
    turn is even eligible for local routing before handing off to
    model_router.resolve_turn_model (tested independently, so it's stubbed
    here rather than re-verified)."""

    def test_stays_on_target_when_no_local_model_configured(self, engine, monkeypatch):
        monkeypatch.setattr(
            "sympose.engine.resolve_turn_model",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")
            ),
        )
        model, routed = engine._select_turn_model(
            "sam", {}, "hi", None, "gemini/gemini-3.6-flash"
        )
        assert (model, routed) == ("gemini/gemini-3.6-flash", False)

    def test_stays_on_target_when_manual_override_active(self, engine, monkeypatch):
        engine.set_model_override("sam", "gemini/gemini-3.6-pro")
        monkeypatch.setattr(
            "sympose.engine.resolve_turn_model",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")
            ),
        )
        model, routed = engine._select_turn_model(
            "sam",
            {"local_model": "ollama/gemma2:9b"},
            "hi",
            None,
            "gemini/gemini-3.6-flash",
        )
        assert (model, routed) == ("gemini/gemini-3.6-flash", False)


class TestBuildSessionHistoryDigest:
    """The zero-round-trip 'what did we do last session?' answer: local JSONL
    session history (SessionManager, ADR-054) injected as ground-truth
    context, same mechanism as vault_ctx — never a vault_read sub-agent."""

    @pytest.fixture(autouse=True)
    def _redirect_sessions_dir(self, tmp_sessions_dir, monkeypatch):
        monkeypatch.setattr(
            "sympose.sessions.resolve_workspace_dir",
            lambda: str(tmp_sessions_dir.parent),
        )

    def test_no_prior_sessions_says_so_and_forbids_vault_spawn(self, engine):
        digest = engine._build_session_history_digest("samantha", None)
        assert "No prior Sympose session is recorded" in digest
        assert "do not spawn" in digest.lower()

    def test_lists_most_recent_session_title(self, engine):
        from sympose.sessions import SessionManager

        sid = SessionManager.create_session("samantha", title="Fix the workspace bug")[
            "session_id"
        ]
        SessionManager.append_turn(sid, "samantha", "hi", "hello")

        digest = engine._build_session_history_digest("samantha", None)
        assert "Fix the workspace bug" in digest
        assert "vault_read" in digest

    def test_excludes_the_active_session(self, engine):
        from sympose.sessions import SessionManager

        old = SessionManager.create_session("samantha", title="Old session")[
            "session_id"
        ]
        SessionManager.append_turn(old, "samantha", "hi", "hello")
        active = SessionManager.create_session("samantha", title="Active session")[
            "session_id"
        ]
        SessionManager.append_turn(active, "samantha", "hi", "hello")

        digest = engine._build_session_history_digest("samantha", active)
        assert "Old session" in digest
        assert "Active session" not in digest

    def test_stays_on_target_when_vault_context_already_resolved(
        self, engine, monkeypatch
    ):
        monkeypatch.setattr(
            "sympose.engine.resolve_turn_model",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")
            ),
        )
        model, routed = engine._select_turn_model(
            "sam",
            {"local_model": "ollama/gemma2:9b"},
            "hi",
            "## Retrieved: some note content",
            "gemini/gemini-3.6-flash",
        )
        assert (model, routed) == ("gemini/gemini-3.6-flash", False)

    def test_stays_on_target_when_message_has_recall_intent(self, engine, monkeypatch):
        monkeypatch.setattr(
            "sympose.engine.resolve_turn_model",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")
            ),
        )
        model, routed = engine._select_turn_model(
            "sam",
            {"local_model": "ollama/gemma2:9b"},
            "pull up my note on Tin",
            None,
            "gemini/gemini-3.6-flash",
        )
        assert (model, routed) == ("gemini/gemini-3.6-flash", False)

    def test_delegates_to_resolve_turn_model_when_eligible(self, engine, monkeypatch):
        captured = {}

        def fake_resolve(target_model, local_model, message, keep_alive=None):
            captured.update(
                target_model=target_model,
                local_model=local_model,
                message=message,
                keep_alive=keep_alive,
            )
            return local_model, True

        monkeypatch.setattr("sympose.engine.resolve_turn_model", fake_resolve)
        model, routed = engine._select_turn_model(
            "sam",
            {"local_model": "ollama/gemma2:9b"},
            "hi there",
            None,
            "gemini/gemini-3.6-flash",
        )
        assert (model, routed) == ("ollama/gemma2:9b", True)
        assert captured == {
            "target_model": "gemini/gemini-3.6-flash",
            "local_model": "ollama/gemma2:9b",
            "message": "hi there",
            "keep_alive": None,
        }

    def test_persona_keep_alive_passed_through(self, engine, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            "sympose.engine.resolve_turn_model",
            lambda target_model, local_model, message, keep_alive=None: (
                captured.update(keep_alive=keep_alive) or (local_model, True)
            ),
        )
        engine._select_turn_model(
            "sam",
            {"local_model": "ollama/gemma2:9b", "keep_alive": "30m"},
            "hi",
            None,
            "gemini/gemini-3.6-flash",
        )
        assert captured["keep_alive"] == "30m"

    def test_config_default_keep_alive_used_when_persona_silent(
        self, engine, monkeypatch
    ):
        engine.config.set("performance.local_keep_alive", "10m")
        captured = {}
        try:
            monkeypatch.setattr(
                "sympose.engine.resolve_turn_model",
                lambda target_model, local_model, message, keep_alive=None: (
                    captured.update(keep_alive=keep_alive) or (local_model, True)
                ),
            )
            engine._select_turn_model(
                "sam",
                {"local_model": "ollama/gemma2:9b"},
                "hi",
                None,
                "gemini/gemini-3.6-flash",
            )
        finally:
            engine.config.set("performance.local_keep_alive", None)
        assert captured["keep_alive"] == "10m"
