"""Meaning-based search behind the `grounding_search` knob (docs/decisions/027). The embedding
model is replaced by a fake whose "meaning" is a handful of concepts, so these tests pin down the
mechanics (which passages are attached, what falls back, what is cached) without Ollama."""

import os
import re
import threading

import pytest

from sympose import settings_store
from sympose.engine import (
    embedding_store,
    embeddings,
    followup,
    grounding,
    reference,
    semantic,
    semantic_refresh,
    similarity,
)

WHOLE = {"vault_folders": ["*"]}
LIBRARY = {"vault_folders": ["*"], "sympose_reference": True}

# word -> the direction it points in; a text with none of them points at the last direction
_CONCEPTS = {
    "database": 0, "storage": 0, "sqlite": 0, "engine": 0, "postgres": 0,
    "pasta": 1, "carbonara": 1, "bacon": 1,
    "vault": 2, "vaults": 2, "another": 2,
    "wagons": 3, "railway": 3,
    "add": 5, "switch": 5,
    "dark": 6, "mode": 6,
}
_NONE = 4  # a text with none of these words points here


def _vector(text: str) -> list[float]:
    v = [0.0] * 7
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in _CONCEPTS:
            v[_CONCEPTS[word]] += 1.0
    if not any(v):
        v[_NONE] = 1.0
    return v


_REAL_EMBED = embeddings.embed  # before the fixture replaces it


@pytest.fixture
def calls():
    return {"embed": [], "build": []}


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch, calls):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    semantic._forget_for_tests()
    semantic_refresh._forget_for_tests()

    def fake_embed(texts, kind, model_name=None):
        calls["embed"].append((kind, list(texts)))
        return [_vector(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    return tmp_path


def _write(tmp_path, rel_path: str, content: str) -> None:
    full = tmp_path / "vault" / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _vault(tmp_path):
    _write(tmp_path, "Atlas.md", "# Atlas\n\nWe use SQLite for the prototype. Postgres was rejected.")
    _write(tmp_path, "Carbonara.md", "# Carbonara\n\nPasta with bacon and egg.")
    _write(tmp_path, "Model Railway.md", "# Model Railway\n\nEleven wagons and two locomotives.")


def _mode(mode, threshold=0.6, margin=1.0):
    """The margin is off (1) unless a test is about it, so the tests of the threshold stay about the threshold."""
    settings_store.set("grounding_search", mode)
    settings_store.set("embedding_min_similarity", threshold)
    settings_store.set("embedding_margin", margin)


# -- the knob and its settings --------------------------------------------------------


def test_keywords_touches_no_embedding_model(setup, calls):
    _vault(setup)
    settings_store.set("grounding_search", "keywords")

    hits = grounding.ground(WHOLE, "what storage engine did we pick?")

    assert hits == []  # no shared word: only meaning would find it
    assert calls["embed"] == []


@pytest.mark.shipped_defaults
def test_the_shipped_default_is_auto_and_finds_a_note_by_meaning(setup):
    _vault(setup)

    assert embeddings.mode() == "auto"
    assert [h["rel_path"] for h in grounding.ground(WHOLE, "what storage engine did we pick?")] == ["Atlas.md"]


@pytest.mark.shipped_defaults
@pytest.mark.parametrize("value", ["semantic", "", 5, True, None, ["embeddings"]])
def test_a_value_that_is_not_a_mode_is_the_default_auto(setup, value):
    settings_store.set("grounding_search", value)
    assert embeddings.mode() == "auto"


@pytest.mark.parametrize("mode", ["auto", "keywords", "embeddings", "hybrid"])
def test_each_mode_is_read_as_it_is_written(setup, mode):
    settings_store.set("grounding_search", mode)
    assert embeddings.mode() == mode


@pytest.mark.parametrize("value", ["0.7", 0, 1, 1.5, -0.2, True, None])
def test_a_threshold_that_is_not_a_number_between_0_and_1_is_the_default(setup, value):
    settings_store.set("embedding_min_similarity", value)
    assert embeddings.min_similarity() == 0.72


@pytest.mark.parametrize("value", ["0.05", -0.01, 1.01, True, None, [0.02]])
def test_a_margin_that_is_not_a_number_from_0_to_1_is_the_default(setup, value):
    settings_store.set("embedding_margin", value)
    assert embeddings.margin() == 0.02


@pytest.mark.parametrize("value, expected", [(0, 0.0), (0.05, 0.05), (1, 1.0)])
def test_a_margin_from_0_to_1_is_read_as_written(setup, value, expected):
    settings_store.set("embedding_margin", value)
    assert embeddings.margin() == expected


def test_a_threshold_and_a_model_are_read_from_the_settings(setup):
    settings_store.set("embedding_min_similarity", 0.75)
    settings_store.set("embedding_model", " ollama/other-embedder ")
    assert embeddings.min_similarity() == 0.75
    assert embeddings.model() == "ollama/other-embedder"


@pytest.mark.parametrize("value", ["", "   ", 3, None])
def test_no_usable_model_name_is_the_default_model(setup, value):
    settings_store.set("embedding_model", value)
    assert embeddings.model() == "ollama/nomic-embed-text"


# -- embeddings mode ---------------------------------------------------------------


def test_meaning_finds_a_note_that_shares_no_word_with_the_message(setup):
    _vault(setup)
    _mode("embeddings")

    hits = grounding.ground(WHOLE, "what storage engine did we pick?")

    assert [h["rel_path"] for h in hits] == ["Atlas.md"]
    assert hits[0]["via"] == "embedding" and hits[0]["matched"] == 2
    assert hits[0]["index"] == 1 and hits[0]["score"] == pytest.approx(1.0, abs=0.01)
    assert "SQLite" in hits[0]["text"]


def test_a_note_that_shares_a_word_but_not_the_meaning_is_not_attached(setup):
    _write(setup, "Priya.md", "# Priya\n\nPriya owns the dark mode decision.")
    _mode("embeddings")

    settings_store.set("grounding_search", "keywords")
    assert [h["rel_path"] for h in grounding.ground(WHOLE, "who is Priya?")] == ["Priya.md"]
    settings_store.set("grounding_search", "embeddings")

    assert grounding.ground(WHOLE, "who is Priya?") == []  # far in meaning from a message with no topic


def test_nothing_close_enough_attaches_nothing(setup):
    _vault(setup)
    _mode("embeddings")

    assert grounding.ground(WHOLE, "good morning") == []


def test_the_threshold_decides_what_is_close_enough(setup):
    _vault(setup)
    _write(setup, "Both.md", "# Both\n\nDatabase notes and pasta notes.")  # half one concept, half another
    _mode("embeddings", threshold=0.95)
    strict = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}
    _mode("embeddings", threshold=0.5)
    loose = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}

    assert strict == {"Atlas.md"}
    assert loose == {"Atlas.md", "Both.md"}


def test_at_most_two_passages_of_a_note_and_the_best_notes_first(setup):
    _write(setup, "Big.md", "# Big\n\nSQLite one.\n\n## A\n\nSQLite two.\n\n## B\n\nSQLite three.")
    _write(setup, "Small.md", "# Small\n\nSQLite and pasta.")
    _mode("embeddings", threshold=0.5)

    hits = grounding.ground(WHOLE, "database storage")

    assert [h["rel_path"] for h in hits].count("Big.md") == 2
    assert hits[0]["rel_path"] == "Big.md" and [h["index"] for h in hits] == list(range(1, len(hits) + 1))


def test_no_more_passages_than_the_caller_takes(setup):
    for i in range(4):
        _write(setup, f"Db{i}.md", f"# Db{i}\n\nSQLite notes {i}.")
    _mode("embeddings", threshold=0.5)

    assert len(grounding.ground(WHOLE, "database", max_results=3)) == 3


# -- the margin and `auto` -----------------------------------------------------------------


def test_only_the_notes_within_the_margin_of_the_best_one_are_attached(setup):
    _vault(setup)
    _write(setup, "Both.md", "# Both\n\nDatabase notes and pasta notes.")  # cosine about 0.71 with "the database"
    _mode("embeddings", threshold=0.5, margin=0.02)
    narrow = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}
    _mode("embeddings", threshold=0.5, margin=0.4)
    wide = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}

    assert narrow == {"Atlas.md"}
    assert wide == {"Atlas.md", "Both.md"}


def test_notes_that_tie_are_all_attached_and_a_margin_of_zero_keeps_only_the_top_score(setup):
    _write(setup, "Atlas.md", "# Atlas\n\nSQLite storage.")
    _write(setup, "Ledger.md", "# Ledger\n\nPostgres storage.")
    _mode("embeddings", threshold=0.5, margin=0.0)

    assert {h["rel_path"] for h in grounding.ground(WHOLE, "the database")} == {"Atlas.md", "Ledger.md"}


def test_the_margin_is_measured_from_the_best_note_that_reaches_the_threshold(setup):
    _vault(setup)
    _write(setup, "Both.md", "# Both\n\nDatabase notes and pasta notes.")
    _mode("embeddings", threshold=0.95, margin=0.02)  # only Atlas reaches it: nothing else to compare with

    assert {h["rel_path"] for h in grounding.ground(WHOLE, "the database")} == {"Atlas.md"}


def test_auto_searches_by_meaning_like_embeddings(setup):
    _vault(setup)
    _mode("auto")

    assert [h["rel_path"] for h in grounding.ground(WHOLE, "what storage engine did we pick?")] == ["Atlas.md"]


def test_auto_without_the_embedding_model_uses_keywords_and_only_notes_it_in_the_log(setup, monkeypatch, caplog):
    _vault(setup)
    _mode("auto")
    _unavailable(monkeypatch)

    with caplog.at_level("INFO"):
        hits = grounding.ground(WHOLE, "carbonara")

    assert [h["rel_path"] for h in hits] == ["Carbonara.md"]
    (record,) = [r for r in caplog.records if "meaning-based search is not available" in r.message]
    assert record.levelname == "INFO"


def test_a_note_made_in_auto_does_not_hide_the_warning_after_switching_to_embeddings(setup, monkeypatch, caplog):
    _vault(setup)
    _unavailable(monkeypatch)
    with caplog.at_level("INFO"):
        _mode("auto")
        grounding.ground(WHOLE, "carbonara")
        semantic._UNAVAILABLE_UNTIL.clear()
        _mode("embeddings")
        grounding.ground(WHOLE, "carbonara")

    levels = [r.levelname for r in caplog.records if "meaning-based search is not available" in r.message]
    assert levels == ["INFO", "WARNING"]


def test_vectors_of_another_size_are_a_misconfiguration_and_warn_even_in_auto(setup, monkeypatch, caplog):
    _vault(setup)
    _mode("auto")
    monkeypatch.setattr(
        embeddings, "embed",
        lambda texts, kind, model_name=None: [[1.0, 0.0, 0.0] if kind == "query" else [1.0, 0.0] for _ in texts],
    )

    with caplog.at_level("INFO"):
        grounding.ground(WHOLE, "carbonara")

    (record,) = [r for r in caplog.records if "another size" in r.message]
    assert record.levelname == "WARNING"


def test_auto_with_a_build_that_cannot_reach_the_model_only_notes_it_in_the_log(setup, monkeypatch, caplog):
    _vault(setup)
    _mode("auto")
    _failing_build(monkeypatch)

    with caplog.at_level("INFO"):
        semantic_refresh.start_build(grounding.scope_index(WHOLE), wait=True)

    (record,) = [r for r in caplog.records if "could not be built" in r.message]
    assert record.levelname == "INFO"


def test_asking_for_embeddings_still_warns_when_the_build_cannot_reach_the_model(setup, monkeypatch, caplog):
    _vault(setup)
    _mode("embeddings")
    _failing_build(monkeypatch)

    with caplog.at_level("INFO"):
        semantic_refresh.start_build(grounding.scope_index(WHOLE), wait=True)

    (record,) = [r for r in caplog.records if "could not be built" in r.message]
    assert record.levelname == "WARNING"


def test_auto_builds_the_index_at_launch_and_keywords_does_not(setup, monkeypatch):
    _vault(setup)
    started = []
    monkeypatch.setattr(semantic_refresh, "start_build", lambda index, **kw: started.append(index))
    monkeypatch.setattr("sympose.profile.resolve_profile", lambda handle: WHOLE)

    def launch():
        semantic_refresh.refresh_in_background("samantha")
        for thread in threading.enumerate():
            if thread.name == "embeddings-samantha":
                thread.join(5)

    _mode("keywords")
    launch()
    assert started == []
    _mode("auto")
    launch()
    assert len(started) >= 1


def test_the_first_turn_after_the_active_vault_changes_starts_the_build_for_the_new_vault(setup, monkeypatch):
    """Nothing is built at the switch itself (a switch in the web app happens in another process than
    the chat), so the turn that first searches the new vault must be what starts its index."""
    from sympose import vault_registry

    for name in ("First", "Second"):
        for i in range(80):  # more passages than a turn embeds on the spot
            _write(setup, f"../{name}/{name} note {i}.md", f"# {name} note {i}\n\nStorage engine number {i} of the {name} vault.")
    monkeypatch.setenv("VAULT_PATHS", f"{setup / 'First'},{setup / 'Second'}")
    started = []
    monkeypatch.setattr(semantic_refresh, "start_build", lambda index, **kw: started.append(index))
    _mode("auto")

    grounding.ground(WHOLE, "what storage engine did we pick?")
    assert {p.rel_path.split(" ")[0] for p in started[-1].passages} == {"First"}
    vault_registry.set_active_vault(str(setup / "Second"))
    grounding.ground(WHOLE, "what storage engine did we pick?")

    assert {p.rel_path.split(" ")[0] for p in started[-1].passages} == {"Second"}


# -- hybrid mode -------------------------------------------------------------------


def test_hybrid_keeps_the_keyword_hit_and_adds_a_note_that_shares_no_word(setup):
    _vault(setup)
    _mode("hybrid", threshold=0.6)

    hits = grounding.ground(WHOLE, "storage railway")

    # Model Railway shares the word "railway" and is close enough in meaning; Atlas shares none
    assert {h["rel_path"]: h["via"] for h in hits} == {"Model Railway.md": "keyword", "Atlas.md": "embedding"}
    assert [h["rel_path"] for h in hits] == ["Model Railway.md", "Atlas.md"]  # keyword hits first


def test_hybrid_keeps_a_keyword_hit_whose_note_is_close_in_meaning(setup):
    _vault(setup)
    _mode("hybrid", threshold=0.6)

    hits = grounding.ground(WHOLE, "SQLite?")

    assert {h["rel_path"]: h["via"] for h in hits} == {"Atlas.md": "keyword"}


def test_hybrid_drops_a_keyword_hit_whose_note_is_far_in_meaning(setup):
    _write(setup, "Priya.md", "# Priya\n\nPriya owns the dark mode decision.")  # no concept: far from the query
    _write(setup, "Atlas.md", "# Atlas\n\nSQLite for the prototype.")
    _mode("hybrid", threshold=0.6)
    settings_store.set("grounding_search", "keywords")
    assert [h["rel_path"] for h in grounding.ground(WHOLE, "who is Priya?")] == ["Priya.md"]
    _mode("hybrid", threshold=0.6)

    assert grounding.ground(WHOLE, "who is Priya?") == []


# -- the library -------------------------------------------------------------------


def test_the_library_is_searched_by_meaning_too_and_a_little_more_loosely(setup):
    _mode("embeddings", threshold=0.6)
    hits = reference.ground(LIBRARY, "how do I add another vault?")

    assert hits and all(h["source"] == "sympose" and h["via"] == "embedding" for h in hits)
    assert all(h["rel_path"].startswith("Sympose reference/") for h in hits)
    assert any(h["rel_path"].endswith("Add or switch vaults.md") for h in hits)


def test_a_persona_without_the_library_never_searches_it_by_meaning(setup, calls):
    _mode("embeddings")

    assert reference.ground(WHOLE, "how do I add another vault?") == []
    assert calls["embed"] == []


# -- fallbacks ---------------------------------------------------------------------


def _unavailable(monkeypatch, message="no such model"):
    def fail(texts, kind, model_name=None):
        raise embeddings.EmbeddingUnavailable(message)

    monkeypatch.setattr(embeddings, "embed", fail)


def test_when_the_embedding_model_is_missing_the_keyword_hits_are_used_and_it_warns_once(
    setup, monkeypatch, caplog
):
    _vault(setup)
    _mode("embeddings")
    _unavailable(monkeypatch)

    with caplog.at_level("WARNING"):
        first = grounding.ground(WHOLE, "carbonara")
        second = grounding.ground(WHOLE, "carbonara")

    assert [h["rel_path"] for h in first] == ["Carbonara.md"] and "via" not in first[0]
    assert first == second
    assert sum("meaning-based search is not available" in r.message for r in caplog.records) == 1


def test_the_index_is_built_in_the_background_when_it_is_too_big_to_do_in_a_turn(setup, monkeypatch, calls):
    for i in range(semantic._SYNC_LIMIT + 1):
        _write(setup, f"Note{i}.md", f"# Note{i}\n\n" + ("Zanzibar spice trade." if i == 0 else f"Filler number {i}."))
    _mode("embeddings")
    started = []
    monkeypatch.setattr(semantic_refresh, "start_build", lambda index, wait=False, model=None: started.append((index, model)))

    hits = grounding.ground(WHOLE, "zanzibar")

    assert len(started) == 1 and started[0][0] is grounding.scope_index(WHOLE)
    assert started[0][1] == "ollama/nomic-embed-text"  # the model the search read, not a later look at the setting
    assert hits and "via" not in hits[0]  # this turn was searched by keyword
    assert all(kind != "query" for kind, _ in calls["embed"])  # and the message was not embedded


def test_a_few_new_passages_are_embedded_on_the_spot_and_kept(setup, calls):
    _vault(setup)
    _mode("embeddings")

    grounding.ground(WHOLE, "storage")
    documents = [text for kind, texts in calls["embed"] if kind == "document" for text in texts]
    assert len(documents) == 3  # one per note, each once

    grounding.ground(WHOLE, "pasta")
    assert len([1 for kind, _ in calls["embed"] if kind == "document"]) == 1  # not again


def test_a_note_that_changed_is_embedded_again_and_the_rest_come_from_the_cache(setup, calls):
    _vault(setup)
    _mode("embeddings")
    grounding.ground(WHOLE, "storage")
    calls["embed"].clear()
    semantic._forget_for_tests()  # a new process: only the cache file is left
    _write(setup, "Carbonara.md", "# Carbonara\n\nPasta with guanciale.")
    later = os.path.getmtime(setup / "vault" / "Carbonara.md") + 10
    os.utime(setup / "vault" / "Carbonara.md", (later, later))

    grounding.ground(WHOLE, "storage")

    documents = [text for kind, texts in calls["embed"] if kind == "document" for text in texts]
    assert len(documents) == 1 and "guanciale" in documents[0]


def test_a_change_of_embedding_model_starts_a_new_cache(setup, calls):
    _vault(setup)
    _mode("embeddings")
    grounding.ground(WHOLE, "storage")
    calls["embed"].clear()
    settings_store.set("embedding_model", "ollama/another")

    grounding.ground(WHOLE, "storage")

    assert len([1 for kind, _ in calls["embed"] if kind == "document"]) == 1  # all three, as one batch


def test_a_hit_by_meaning_is_strong_evidence_and_asks_for_no_rewrite(setup):
    _vault(setup)
    _mode("embeddings")

    def rewriter(*args):
        raise AssertionError("the rewrite step should not run for a hit found by meaning")

    hits, searched = followup.ground(WHOLE, "what storage engine did we pick?", [], "ollama_chat/x", None, rewriter)

    assert [h["rel_path"] for h in hits] == ["Atlas.md"] and searched is None


def test_a_hit_by_meaning_says_whether_its_passage_is_text_or_a_title():
    from sympose.engine import semantic_pick
    from sympose.engine.grounding_index import build_index

    passages = build_index(
        [
            {"rel_path": "Body.md", "file_name": "Body.md", "meta": {}, "body": "Some words in a body."},
            {"rel_path": "Card.md", "file_name": "Card.md", "meta": {}, "body": ""},
        ]
    ).passages

    assert {p.rel_path: semantic_pick.hit(p, 0.9, "embedding")["kind"] for p in passages} == {
        "Body.md": "text",
        "Card.md": "title",
    }


# -- the cache file ------------------------------------------------------------------


def test_vectors_survive_the_cache_and_a_missing_key_is_absent(setup):
    k1, k2 = embedding_store.key("m", "one"), embedding_store.key("m", "two")
    embedding_store.save({k1: [0.25, -0.5, 1.0]})

    loaded = embedding_store.load([k1, k2])

    assert list(loaded) == [k1] and loaded[k1] == pytest.approx([0.25, -0.5, 1.0])


def test_the_key_depends_on_the_model_and_the_text(setup):
    assert embedding_store.key("a", "x") != embedding_store.key("b", "x")
    assert embedding_store.key("a", "x") != embedding_store.key("a", "y")
    assert embedding_store.key("a", "x") == embedding_store.key("a", "x")


def test_a_damaged_cache_file_means_no_cache_not_a_failed_search(setup):
    _vault(setup)
    _mode("embeddings")
    with open(embedding_store.path(), "wb") as f:
        f.write(b"this is not a database")

    hits = grounding.ground(WHOLE, "what storage engine did we pick?")

    assert [h["rel_path"] for h in hits] == ["Atlas.md"]


def test_the_cache_sits_beside_the_settings_file(setup):
    assert os.path.dirname(embedding_store.path()) == str(setup)
    assert os.path.basename(embedding_store.path()) == "embedding_cache.sqlite"


# -- the background build ------------------------------------------------------------


def test_a_build_embeds_only_the_passages_without_a_vector(setup, calls):
    _vault(setup)
    _mode("embeddings")
    index = grounding.scope_index(WHOLE)

    semantic_refresh.build(index)
    assert sum(len(texts) for _, texts in calls["embed"]) == 3
    calls["embed"].clear()
    semantic_refresh.build(index)

    assert calls["embed"] == []


def test_two_builds_of_the_same_index_do_not_run_at_once(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    release, running = threading.Event(), []

    def slow_build(idx, token=None):
        running.append(idx)
        release.wait(5)

    monkeypatch.setattr(semantic_refresh, "build", slow_build)
    first = semantic_refresh.start_build(index)
    second = semantic_refresh.start_build(index)
    release.set()
    first.join(5)

    assert second is None and len(running) == 1


def _failing_build(monkeypatch):
    attempts = []

    def build(idx, token=None):
        attempts.append(idx)
        raise embeddings.EmbeddingUnavailable("down")

    monkeypatch.setattr(semantic_refresh, "build", build)
    return attempts


def test_a_failed_build_does_not_raise_and_is_not_started_again_on_every_turn(setup, monkeypatch, caplog):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    attempts = _failing_build(monkeypatch)

    with caplog.at_level("WARNING"):
        first = semantic_refresh.start_build(index, wait=True)
        second = semantic_refresh.start_build(index, wait=True)

    assert first is not None and second is None and len(attempts) == 1
    assert sum("could not be built" in r.message for r in caplog.records) == 1


def test_a_failed_build_is_tried_again_after_a_while(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    attempts = _failing_build(monkeypatch)
    semantic_refresh.start_build(index, wait=True)
    monkeypatch.setattr(semantic_refresh, "_RETRY_AFTER_SECONDS", 0.0)

    semantic_refresh.start_build(index, wait=True)

    assert len(attempts) == 2


def test_an_unexpected_error_in_a_build_is_contained_and_counts_as_a_failure(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    monkeypatch.setattr(semantic_refresh, "build", lambda idx, token=None: 1 / 0)

    assert semantic_refresh.start_build(index, wait=True) is not None
    assert semantic_refresh.start_build(index, wait=True) is None  # failed, so not at once again


def test_a_cache_that_cannot_be_written_does_not_restart_the_build_every_turn(setup, monkeypatch, calls):
    for i in range(semantic._SYNC_LIMIT + 1):
        _write(setup, f"Note{i}.md", f"# Note{i}\n\nFiller number {i}.")
    _mode("embeddings")
    monkeypatch.setattr(embedding_store, "save", lambda vectors: False)

    for _ in range(3):
        grounding.ground(WHOLE, "filler")
        _wait_for_threads("embedding-index")

    documents = [1 for kind, _ in calls["embed"] if kind == "document"]
    assert len(documents) == 1  # one attempt, not one per turn


def _wait_for_threads(prefix):
    for thread in threading.enumerate():
        if thread.name.startswith(prefix):
            thread.join(10)


def test_the_refresh_at_launch_does_nothing_with_the_default_knob(setup, calls, monkeypatch):
    _vault(setup)
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(setup / "profiles"))

    semantic_refresh.refresh_in_background("samantha")
    _wait_for_threads("embeddings-")

    assert calls["embed"] == [] and not os.path.exists(embedding_store.path())


def test_the_refresh_at_launch_builds_the_notes_and_the_library_when_the_knob_is_on(setup, calls, monkeypatch):
    from helpers import write_persona

    _vault(setup)
    profiles = setup / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: true\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    _mode("embeddings")

    semantic_refresh.refresh_in_background("samantha")
    _wait_for_threads("embeddings-")

    texts = [text for _, batch in calls["embed"] for text in batch]
    assert any("SQLite" in t for t in texts) and any("Add or switch vaults" in t for t in texts)
    assert all(kind == "document" for kind, _ in calls["embed"])


def test_the_refresh_for_an_unknown_persona_is_quiet(setup, calls, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(setup / "profiles"))
    _mode("embeddings")

    semantic_refresh.refresh_in_background("nobody")
    _wait_for_threads("embeddings-")

    assert calls["embed"] == []


# -- what the model is sent for a query and a passage --------------------------------


def _litellm_answering(sent):
    class Response:
        data = [{"embedding": [1.0, 0.0]}]

    return lambda model, input, **kw: sent.append((model, input)) or Response()


def test_the_nomic_prefixes_are_added_for_that_model_only(setup, monkeypatch):
    sent: list = []
    monkeypatch.setattr(embeddings, "embed", _REAL_EMBED)
    monkeypatch.setattr(embeddings.litellm, "embedding", _litellm_answering(sent))

    embeddings.embed(["hello"], "query")
    embeddings.embed(["hello"], "document")
    settings_store.set("embedding_model", "ollama/some-other-model")
    embeddings.embed(["hello"], "query")

    assert sent[0] == ("ollama/nomic-embed-text", ["search_query: hello"])
    assert sent[1] == ("ollama/nomic-embed-text", ["search_document: hello"])
    assert sent[2] == ("ollama/some-other-model", ["hello"])


def test_texts_are_sent_in_batches_and_come_back_in_order(setup, monkeypatch):
    sent: list = []
    monkeypatch.setattr(embeddings, "embed", _REAL_EMBED)

    def answer(model, input, **kw):
        sent.append(list(input))
        return type("R", (), {"data": [{"embedding": [float(len(t))]} for t in input]})()

    monkeypatch.setattr(embeddings.litellm, "embedding", answer)
    texts = ["x" * (i + 1) for i in range(20)]

    vectors = embeddings.embed(texts, "document")

    assert [len(batch) for batch in sent] == [16, 4]
    assert [v[0] for v in vectors] == [float(len("search_document: ") + len(t)) for t in texts]


def test_any_error_from_the_embedding_call_means_unavailable(setup, monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _REAL_EMBED)

    def boom(model, input, **kw):
        raise ConnectionError("Ollama is not running")

    monkeypatch.setattr(embeddings.litellm, "embedding", boom)

    with pytest.raises(embeddings.EmbeddingUnavailable, match="Ollama is not running"):
        embeddings.embed(["hello"], "query")


def test_the_wrong_number_of_vectors_means_unavailable(setup, monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _REAL_EMBED)
    monkeypatch.setattr(
        embeddings.litellm, "embedding", lambda model, input, **kw: type("R", (), {"data": []})()
    )

    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed(["hello"], "query")


def test_unit_vectors_have_length_one_and_a_zero_vector_stays_zero(setup):
    assert embeddings.dot(embeddings.unit([3.0, 4.0]), embeddings.unit([3.0, 4.0])) == pytest.approx(1.0)
    assert list(embeddings.unit([0.0, 0.0])) == [0.0, 0.0]
    assert embeddings.dot(embeddings.unit([1.0, 0.0]), embeddings.unit([0.0, 1.0])) == 0.0


# -- the exact thresholds ------------------------------------------------------------


def _one_passage_index(rel_path="Note.md"):
    from collections import Counter

    from sympose.engine.grounding_index import Index, Passage

    passage = Passage(rel_path, "Note", "Note", "text", (), Counter(), 1, (), frozenset())
    return Index([passage], {}, 1, 1.0)


def _similarity_of(monkeypatch, similarity: float):
    """A fake embedder for which the message and the one passage have exactly this cosine."""
    def embed(texts, kind, model_name=None):
        if kind == "query":
            return [[1.0, 0.0] for _ in texts]
        return [[similarity, (1 - similarity**2) ** 0.5] for _ in texts]

    monkeypatch.setattr(embeddings, "embed", embed)


@pytest.mark.parametrize("similarity, vault, library", [(0.69, False, False), (0.71, False, True), (0.73, True, True)])
def test_the_library_needs_a_little_less_similarity_than_the_users_notes(setup, monkeypatch, similarity, vault, library):
    settings_store.set("grounding_search", "embeddings")  # the default threshold, 0.72
    _similarity_of(monkeypatch, similarity)

    in_vault = semantic.refine(_one_passage_index(), "message", [], library=False)
    in_library = semantic.refine(_one_passage_index("Lib.md"), "message", [], library=True)

    assert bool(in_vault) is vault and bool(in_library) is library


@pytest.mark.parametrize("similarity, kept, added", [(0.65, False, False), (0.67, True, False), (0.71, True, True)])
def test_hybrid_keeps_a_keyword_hit_within_0_06_and_adds_a_note_within_0_02(setup, monkeypatch, similarity, kept, added):
    settings_store.set("grounding_search", "hybrid")  # 0.72: keep from 0.66, add from 0.70
    _similarity_of(monkeypatch, similarity)
    keyword_hit = {"rel_path": "Note.md", "text": "text", "matched": 3}

    with_keyword = semantic.refine(_one_passage_index(), "message", [keyword_hit])
    without_keyword = semantic.refine(_one_passage_index(), "message", [])

    assert bool(with_keyword) is (kept or added)
    if kept and not added:
        assert with_keyword[0]["via"] == "keyword" and with_keyword[0]["matched"] == 3
    assert bool(without_keyword) is added


@pytest.mark.parametrize("mode, attached", [("auto", False), ("embeddings", False), ("hybrid", True)])
def test_auto_does_not_keep_a_keyword_hit_that_is_only_nearly_close_in_meaning(setup, monkeypatch, mode, attached):
    settings_store.set("grounding_search", mode)  # threshold 0.72; hybrid would keep a keyword hit from 0.66
    _similarity_of(monkeypatch, 0.67)
    keyword_hit = {"rel_path": "Note.md", "text": "text", "matched": 3}

    assert bool(semantic.refine(_one_passage_index(), "message", [keyword_hit])) is attached


# -- a clear winner just under the threshold ---------------------------------------------


def _two_notes(monkeypatch, first: float, second: float):
    """An index of two notes whose cosines with the message are exactly `first` and `second`."""
    from collections import Counter

    from sympose.engine.grounding_index import Index, Passage

    def passage(rel_path):
        return Passage(rel_path, rel_path[:-3], rel_path[:-3], rel_path[:-3], (), Counter(), 1, (), frozenset())

    def unit_at(cosine):
        return [cosine, (1 - cosine**2) ** 0.5]

    by_text = {"A": unit_at(first), "B": unit_at(second)}

    def embed(texts, kind, model_name=None):
        return [[1.0, 0.0] if kind == "query" else by_text[t.split("\n")[0]] for t in texts]

    monkeypatch.setattr(embeddings, "embed", embed)
    return Index([passage("A.md"), passage("B.md")], {}, 2, 1.0)


@pytest.mark.parametrize(
    "first, second, attached",
    [
        (0.69, 0.60, True),   # 0.03 under 0.72, 0.09 ahead
        (0.69, 0.64, False),  # only 0.05 ahead
        (0.67, 0.55, False),  # 0.05 under the threshold
        (0.75, 0.60, True),   # over the threshold: the ordinary way
    ],
)
def test_a_note_just_under_the_threshold_is_attached_when_it_is_clearly_ahead(setup, monkeypatch, first, second, attached):
    settings_store.set("grounding_search", "embeddings")  # 0.72, margin 0.02
    index = _two_notes(monkeypatch, first, second)

    hits = semantic.refine(index, "message", [])

    assert [h["rel_path"] for h in hits] == (["A.md"] if attached else [])


def test_the_clear_winner_rule_adds_nothing_when_a_note_reaches_the_threshold(setup, monkeypatch):
    settings_store.set("grounding_search", "embeddings")
    index = _two_notes(monkeypatch, 0.73, 0.60)

    assert [h["rel_path"] for h in semantic.refine(index, "message", [])] == ["A.md"]


def test_one_note_alone_is_not_a_clear_winner(setup, monkeypatch):
    settings_store.set("grounding_search", "embeddings")
    _similarity_of(monkeypatch, 0.70)

    assert semantic.refine(_one_passage_index(), "message", []) == []


def test_the_clear_winner_rule_is_for_meaning_only_and_auto_not_hybrid(setup, monkeypatch):
    index = _two_notes(monkeypatch, 0.69, 0.60)
    results = {}
    for mode in ("auto", "embeddings", "hybrid"):
        settings_store.set("grounding_search", mode)
        results[mode] = [h["rel_path"] for h in semantic.refine(index, "message", [])]

    assert results == {"auto": ["A.md"], "embeddings": ["A.md"], "hybrid": []}


def test_the_library_uses_its_own_lower_bar_for_the_clear_winner_too(setup, monkeypatch):
    settings_store.set("grounding_search", "embeddings")  # library bar 0.70: 0.67 is 0.03 under it
    index = _two_notes(monkeypatch, 0.67, 0.55)

    assert [h["rel_path"] for h in semantic.refine(index, "message", [], library=True)] == ["A.md"]
    assert semantic.refine(index, "message", [], library=False) == []  # 0.05 under 0.72


@pytest.mark.parametrize(
    "mode, library, attached",
    [("auto", True, True), ("auto", False, False), ("embeddings", True, False), ("hybrid", False, True)],
)
def test_under_auto_the_library_keeps_a_keyword_hit_that_is_nearly_close_in_meaning(setup, monkeypatch, mode, library, attached):
    """The library is small and its notes are question headings, so a word in common is strong evidence there
    (docs/decisions/027): `auto` searches it like `hybrid` and searches the user's notes by meaning only."""
    settings_store.set("grounding_search", mode)  # bars: notes 0.72, library 0.70; hybrid keeps from 0.06 under
    _similarity_of(monkeypatch, 0.66)
    keyword_hit = {"rel_path": "Note.md", "text": "text", "matched": 3}

    hits = semantic.refine(_one_passage_index(), "message", [keyword_hit], library=library)

    assert bool(hits) is attached


def test_hybrid_adds_a_better_passage_of_a_note_that_a_keyword_hit_already_brought(setup, monkeypatch):
    """The library keeps many answers in one note: a keyword hit on one of them must not hide the passage
    that is closest in meaning."""
    from collections import Counter

    from sympose.engine.grounding_index import Index, Passage

    def passage(heading):
        return Passage("Notes.md", "Notes", heading, heading, (), Counter(), 1, (), frozenset())

    def embed(texts, kind, model_name=None):
        near = {"Near": [0.95, 0.312], "Word": [0.8, 0.6]}
        return [[1.0, 0.0] if kind == "query" else near[t.split("\n")[1]] for t in texts]

    monkeypatch.setattr(embeddings, "embed", embed)
    settings_store.set("grounding_search", "hybrid")
    index = Index([passage("Word"), passage("Near")], {}, 2, 1.0)
    keyword_hit = {"rel_path": "Notes.md", "heading": "Word", "text": "Word", "matched": 3}

    hits = semantic.refine(index, "message", [keyword_hit])

    assert [(h["heading"], h["via"]) for h in hits] == [("Word", "keyword"), ("Near", "embedding")]


# -- the turn record and the cache's edges --------------------------------------------


def _turn_setup(setup, monkeypatch):
    from helpers import write_persona

    from sympose.engine import model as model_mod
    from sympose.engine import turn

    profiles = setup / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setattr(model_mod, "call_model", lambda messages, model=None, **k: model_mod.ModelReply("ok", 5))
    return turn


def _recorded(turn, session):
    result = turn.run_turn("samantha", "what storage engine did we pick?")
    return session.load_session("samantha", result.session_id)["turns"][-1]["sent"]["notes"]


def test_the_turn_record_says_how_each_note_was_found_only_when_the_knob_is_on(setup, monkeypatch):
    from sympose.engine import session

    _vault(setup)
    turn = _turn_setup(setup, monkeypatch)
    _mode("embeddings")

    on = _recorded(turn, session)
    settings_store.set("grounding_search", "keywords")
    off = _recorded(turn, session)

    assert on == [{"path": "Atlas.md", "heading": "Atlas", "source": "vault", "via": "embedding"}]
    assert off == []


def test_more_vectors_than_one_query_can_hold_are_all_loaded(setup):
    keys = [embedding_store.key("m", str(i)) for i in range(1200)]
    embedding_store.save({k: [float(i), 1.0] for i, k in enumerate(keys)})

    loaded = embedding_store.load(keys)

    assert len(loaded) == 1200 and loaded[keys[1199]] == pytest.approx([1199.0, 1.0])


def test_a_long_passage_is_cut_before_it_is_embedded(setup):
    from types import SimpleNamespace

    passage = SimpleNamespace(title="T", heading="H", text="x" * 5000, kind="text")

    text = embeddings.passage_text(passage)

    assert len(text) == 1500 and text.startswith("T\nH\nxxx")


def test_the_aliases_of_a_title_passage_are_embedded_as_other_names_of_the_note():
    from sympose.engine.grounding_index import build_index

    [passage] = build_index(
        [{"rel_path": "A.md", "file_name": "Anna Ruiz.md", "meta": {"aliases": ["Annie", "A. Ruiz"]}, "body": ""}]
    ).passages

    assert embeddings.passage_text(passage) == "Anna Ruiz\n\nalso called Annie, A. Ruiz"


def test_a_title_passage_with_no_aliases_or_headings_is_embedded_as_its_title():
    from sympose.engine.grounding_index import build_index

    [passage] = build_index([{"rel_path": "A.md", "file_name": "Anna Ruiz.md", "meta": {}, "body": ""}]).passages

    assert embeddings.passage_text(passage) == "Anna Ruiz\n\n"


def _index_of(*passages):
    from collections import Counter

    from sympose.engine.grounding_index import Index, Passage

    made = [Passage(path, "Note", "Note", text, (), Counter(), 1, (), frozenset()) for path, text in passages]
    return Index(made, {}, len({p[0] for p in passages}), 1.0)


def test_a_notes_closeness_is_that_of_its_best_passage_not_its_last(setup, monkeypatch):
    settings_store.set("grounding_search", "hybrid")

    def embed(texts, kind, model_name=None):
        if kind == "query":
            return [[1.0, 0.0] for _ in texts]
        return [[0.9, 0.436] if "near" in t else [0.1, 0.995] for t in texts]

    monkeypatch.setattr(embeddings, "embed", embed)
    index = _index_of(("Note.md", "the near part"), ("Note.md", "the far part"))  # the far one is last

    hits = semantic.refine(index, "message", [{"rel_path": "Note.md", "text": "the far part", "matched": 2}])

    # kept although its own passage is far (the note's best passage is close), and the near passage follows it
    assert [(h["via"], h["text"]) for h in hits] == [("keyword", "the far part"), ("embedding", "the near part")]


def test_keyword_hits_and_notes_found_by_meaning_together_never_pass_the_limit(setup, monkeypatch):
    settings_store.set("grounding_search", "hybrid")
    monkeypatch.setattr(
        embeddings, "embed",
        lambda texts, kind, model_name=None: [[1.0, 0.0] if kind == "query" else [0.69, 0.724] for _ in texts],
    )
    index = _index_of(*[(f"N{i}.md", f"text {i}") for i in range(6)])  # all equally close
    keyword_hits = [{"rel_path": f"N{i}.md", "text": "t", "matched": 2} for i in range(2, 6)]

    hits = semantic.refine(index, "message", keyword_hits, max_results=4)

    # the four keyword hits fill the limit; N0 and N1, close in meaning, do not push past it
    assert [(h["rel_path"], h["via"]) for h in hits] == [(f"N{i}.md", "keyword") for i in range(2, 6)]
    assert [h["index"] for h in hits] == [1, 2, 3, 4]


def test_a_failed_embedding_call_does_not_print_litellms_banner(setup, monkeypatch):
    assert embeddings.litellm.suppress_debug_info is True


# -- what the review found ---------------------------------------------------------------


def test_the_embedding_call_has_a_timeout_so_a_hung_ollama_falls_back(setup, monkeypatch):
    seen = {}
    monkeypatch.setattr(embeddings, "embed", _REAL_EMBED)
    monkeypatch.setattr(
        embeddings.litellm, "embedding",
        lambda model, input, **kw: seen.update(kw) or type("R", (), {"data": [{"embedding": [1.0]}]})(),
    )

    embeddings.embed(["hello"], "query")

    assert seen == {"timeout": 30}


def test_a_build_keeps_the_model_it_started_with_when_the_setting_is_edited_meanwhile(setup, monkeypatch):
    for i in range(70):  # two batches
        _write(setup, f"Note{i}.md", f"# Note{i}\n\nFiller number {i}.")
    index = grounding.scope_index(WHOLE)
    used = []

    def embed(texts, kind, model_name=None):
        used.append(model_name)
        settings_store.set("embedding_model", "ollama/edited-meanwhile")
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(embeddings, "embed", embed)

    semantic_refresh.build(index)

    assert used == ["ollama/nomic-embed-text", "ollama/nomic-embed-text"]
    keys = [embedding_store.key("ollama/nomic-embed-text", embeddings.passage_text(p)) for p in index.passages]
    assert len(embedding_store.load(keys)) == len(keys)  # every vector under the model that made it


def test_vectors_of_another_size_than_the_message_fall_back_to_keywords(setup, monkeypatch):
    _vault(setup)
    _mode("embeddings")
    monkeypatch.setattr(
        embeddings, "embed",
        lambda texts, kind, model_name=None: [[1.0, 0.0, 0.0] if kind == "query" else [1.0, 0.0] for _ in texts],
    )

    hits = grounding.ground(WHOLE, "carbonara")

    assert [h["rel_path"] for h in hits] == ["Carbonara.md"] and "via" not in hits[0]


def test_vectors_are_kept_as_32_bit_floats_with_or_without_numpy(setup, monkeypatch):
    from array import array

    _vault(setup)
    _mode("embeddings")
    grounding.ground(WHOLE, "storage")
    [(_, vectors)] = list(semantic._CACHE.values())

    if similarity.numpy is not None:
        assert str(vectors.unit_vectors._matrix.dtype) == "float32"
    monkeypatch.setattr(similarity, "numpy", None)
    plain = similarity.VectorSet([embeddings.unit([3.0, 4.0])])
    assert all(isinstance(row, array) and row.typecode == "f" for row in plain._rows)


def test_only_the_last_few_indexes_are_kept_in_memory(setup):
    _vault(setup)
    _mode("embeddings")
    for i in range(7):
        _write(setup, f"Extra{i}.md", f"# Extra{i}\n\nPasta number {i}.")  # a new index each time
        grounding.ground(WHOLE, "storage")

    assert len(semantic._CACHE) == 4


def test_the_search_asks_for_every_vector_from_the_model_it_read_once(setup, monkeypatch):
    _vault(setup)
    _mode("embeddings")
    settings_store.set("embedding_model", "ollama/chosen")
    asked = []

    def embed(texts, kind, model_name=None):
        asked.append((kind, model_name))
        return [_vector(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed", embed)

    grounding.ground(WHOLE, "storage")

    assert sorted(set(asked)) == [("document", "ollama/chosen"), ("query", "ollama/chosen")]


def test_saving_says_whether_the_cache_could_be_written(setup, monkeypatch, tmp_path):
    assert embedding_store.save({}) is True
    assert embedding_store.save({"k": [1.0]}) is True

    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the cache folder should be")
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(blocker / "settings.json"))

    assert embedding_store.save({"k": [1.0]}) is False


# -- the progress the CLI shows -------------------------------------------------------


def test_no_build_running_means_no_progress(setup):
    assert semantic_refresh.progress() is None


def _notes(setup, count):
    for i in range(count):
        _write(setup, f"Note{i}.md", f"# Note{i}\n\nFiller number {i}.")


def test_a_build_reports_how_much_of_what_it_had_to_do_is_done(setup, monkeypatch):
    _notes(setup, 130)  # three batches of 64, 64, 2
    index = grounding.scope_index(WHOLE)
    token = ("ollama/nomic-embed-text", id(index))
    seen = []

    def embed(texts, kind, model_name=None):
        seen.append(semantic_refresh.progress())
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(embeddings, "embed", embed)
    semantic_refresh._BUILDING.add(token)  # what start_build does before the thread runs

    semantic_refresh.build(index, token)

    assert seen == [0, 49, 98]  # before each batch: 0, 64 and 128 of 130
    assert semantic_refresh.progress() == 100


def test_progress_covers_every_build_running_and_goes_when_they_end(setup, monkeypatch):
    first, second = ("m", 1), ("m", 2)
    semantic_refresh._BUILDING.update({first, second})
    semantic_refresh._report(first, 50, 100)
    semantic_refresh._report(second, 0, 300)

    assert semantic_refresh.progress() == 12  # 50 of 400

    semantic_refresh._BUILDING.clear()
    assert semantic_refresh.progress() is None


def test_a_build_that_has_not_counted_its_work_or_has_none_is_not_indexing(setup):
    semantic_refresh._BUILDING.add(("m", 1))
    assert semantic_refresh.progress() is None  # not counted yet

    semantic_refresh._report(("m", 1), 0, 0)
    assert semantic_refresh.progress() is None  # a warm cache: nothing to embed

    semantic_refresh._BUILDING.add(("m", 2))
    semantic_refresh._report(("m", 2), 30, 100)
    assert semantic_refresh.progress() == 30  # only the build with work counts


def test_a_build_with_a_warm_cache_never_shows_as_indexing(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    semantic_refresh.build(index)  # warms the cache
    token = ("ollama/nomic-embed-text", id(index))
    semantic_refresh._BUILDING.add(token)
    seen = []
    monkeypatch.setattr(embedding_store, "load", lambda keys, real=embedding_store.load: seen.append(semantic_refresh.progress()) or real(keys))

    semantic_refresh.build(index, token)

    assert seen and set(seen) == {None}
    assert semantic_refresh.progress() is None


def test_a_finished_or_failed_build_leaves_no_progress_behind(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)

    semantic_refresh.start_build(index, wait=True)

    assert semantic_refresh.progress() is None and semantic_refresh._PROGRESS == {}


# -- what the second review found ------------------------------------------------------


def test_a_damaged_row_in_the_cache_is_a_missing_vector_not_a_failed_search(setup):
    import sqlite3

    good, bad = embedding_store.key("m", "good"), embedding_store.key("m", "bad")
    embedding_store.save({good: [1.0, 2.0]})
    conn = sqlite3.connect(embedding_store.path())
    with conn:
        conn.execute("INSERT INTO vectors (key, vec) VALUES (?, ?)", (bad, b"abcde"))  # 5 bytes: not whole floats
    conn.close()

    loaded = embedding_store.load([good, bad])

    assert list(loaded) == [good]


def test_a_search_over_a_cache_with_a_damaged_row_embeds_that_passage_again(setup, calls):
    import sqlite3

    _vault(setup)
    _mode("embeddings")
    index = grounding.scope_index(WHOLE)
    passage = index.passages[0]
    key = embedding_store.key("ollama/nomic-embed-text", embeddings.passage_text(passage))
    embedding_store.save({key: [1.0]})
    conn = sqlite3.connect(embedding_store.path())
    with conn:
        conn.execute("UPDATE vectors SET vec = ? WHERE key = ?", (b"abcde", key))
    conn.close()

    hits = grounding.ground(WHOLE, "what storage engine did we pick?")

    assert [h["rel_path"] for h in hits] == ["Atlas.md"]
    assert len(embedding_store.load([key])) == 1  # and the row is whole again


def test_a_failure_is_remembered_with_its_index_and_old_ones_are_forgotten(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    _failing_build(monkeypatch)
    semantic_refresh.start_build(index, wait=True)
    token = ("ollama/nomic-embed-text", id(index))

    assert semantic_refresh._FAILED[token][1] is index  # held, so its id cannot be given to another index

    monkeypatch.setattr(semantic_refresh, "_RETRY_AFTER_SECONDS", 0.0)
    other = _index_of(("Other.md", "text"))
    semantic_refresh.start_build(other, wait=True)

    assert list(semantic_refresh._FAILED) == [("ollama/nomic-embed-text", id(other))]  # the old entry was let go


def test_a_build_uses_the_model_it_was_started_for_not_the_one_in_the_settings_now(setup, monkeypatch):
    _vault(setup)
    index = grounding.scope_index(WHOLE)
    used = []
    monkeypatch.setattr(
        embeddings, "embed", lambda texts, kind, model_name=None: used.append(model_name) or [[1.0, 0.0] for _ in texts]
    )
    settings_store.set("embedding_model", "ollama/changed-since")

    semantic_refresh.start_build(index, wait=True, model="ollama/started-with")

    assert used == ["ollama/started-with"]


def test_many_turns_at_once_do_not_corrupt_the_cache_of_indexes(setup):
    settings_store.set("grounding_search", "embeddings")
    errors = []

    def turn(n):
        try:
            for i in range(25):
                semantic._vectors_for(_index_of((f"N{n}-{i}.md", f"text {n} {i}")), 64, "ollama/nomic-embed-text")
        except Exception as e:  # noqa: BLE001 - any error is the failure
            errors.append(e)

    threads = [threading.Thread(target=turn, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert errors == [] and len(semantic._CACHE) <= 4


# -- the scan, with and without numpy ----------------------------------------------------


def _unit_rows(count=40, dims=16):
    import random

    rng = random.Random(7)
    return [embeddings.unit([rng.uniform(-1, 1) for _ in range(dims)]) for _ in range(count)]


def test_the_scan_gives_the_cosine_of_each_vector_in_the_order_given(setup, monkeypatch):
    monkeypatch.setattr(similarity, "numpy", None)
    rows = [embeddings.unit([1.0, 0.0]), embeddings.unit([0.0, 1.0]), embeddings.unit([1.0, 1.0])]

    scores = similarity.VectorSet(rows).scores(embeddings.unit([1.0, 0.0]))

    assert scores == pytest.approx([1.0, 0.0, 0.7071], abs=1e-4)


def test_numpy_and_the_plain_loop_give_the_same_scores(setup, monkeypatch):
    pytest.importorskip("numpy")
    rows, query = _unit_rows(), embeddings.unit(_unit_rows(1)[0])
    fast = similarity.VectorSet(rows)
    monkeypatch.setattr(similarity, "numpy", None)
    plain = similarity.VectorSet(rows)

    assert fast._matrix is not None and plain._matrix is None
    assert fast.scores(query) == pytest.approx(plain.scores(query), abs=1e-6)
    assert fast.dims == plain.dims == 16


def test_an_empty_set_has_no_dimensions_and_no_scores(setup, monkeypatch):
    assert similarity.VectorSet([]).dims == 0 and similarity.VectorSet([]).scores([1.0]) == []
    monkeypatch.setattr(similarity, "numpy", None)
    assert similarity.VectorSet([]).dims == 0 and similarity.VectorSet([]).scores([1.0]) == []


def test_the_search_gives_the_same_answers_without_numpy(setup, monkeypatch):
    monkeypatch.setattr(similarity, "numpy", None)
    _vault(setup)
    _write(setup, "Both.md", "# Both\n\nDatabase notes and pasta notes.")
    _mode("embeddings", threshold=0.95)
    strict = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}
    _mode("embeddings", threshold=0.5)
    loose = {h["rel_path"] for h in grounding.ground(WHOLE, "the database")}
    _mode("hybrid", threshold=0.6)
    hybrid = {h["rel_path"]: h["via"] for h in grounding.ground(WHOLE, "storage railway")}

    assert strict == {"Atlas.md"} and loose == {"Atlas.md", "Both.md"}
    assert hybrid == {"Model Railway.md": "keyword", "Atlas.md": "embedding"}
    assert [v.unit_vectors._matrix for _, v in semantic._CACHE.values()] == [None]


def test_vectors_of_another_size_still_fall_back_without_numpy(setup, monkeypatch):
    monkeypatch.setattr(similarity, "numpy", None)
    _vault(setup)
    _mode("embeddings")
    monkeypatch.setattr(
        embeddings, "embed",
        lambda texts, kind, model_name=None: [[1.0, 0.0, 0.0] if kind == "query" else [1.0, 0.0] for _ in texts],
    )

    hits = grounding.ground(WHOLE, "carbonara")

    assert [h["rel_path"] for h in hits] == ["Carbonara.md"] and "via" not in hits[0]


# -- what the third review found -----------------------------------------------------------


def test_a_failure_starting_the_background_index_is_logged_not_thrown_over_the_terminal(setup, monkeypatch, caplog):
    thrown = []
    monkeypatch.setattr(threading, "excepthook", lambda args: thrown.append(args))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(setup / "profiles"))
    from helpers import write_persona

    write_persona(setup / "profiles", "samantha", "name: Samantha\nvault_folders: '*'\n")
    _mode("embeddings")
    monkeypatch.setattr(grounding, "scope_index", lambda persona: (_ for _ in ()).throw(OSError("unreadable vault")))

    with caplog.at_level("ERROR"):
        semantic_refresh.refresh_in_background("samantha")
        _wait_for_threads("embeddings-")

    assert thrown == [] and any("Could not start the search index" in r.message for r in caplog.records)


def _token(index):
    return ("ollama/nomic-embed-text", id(index))


def test_while_a_build_runs_a_turn_searches_by_keyword_without_reading_the_cache(setup, monkeypatch, calls):
    _vault(setup)
    _mode("embeddings")
    index = grounding.scope_index(WHOLE)
    semantic_refresh._BUILDING.add(_token(index))
    monkeypatch.setattr(embedding_store, "load", lambda keys: (_ for _ in ()).throw(AssertionError("cache read")))

    hits = grounding.ground(WHOLE, "carbonara")

    assert [h["rel_path"] for h in hits] == ["Carbonara.md"] and "via" not in hits[0]
    assert calls["embed"] == []


def test_after_a_failed_build_a_turn_does_not_read_the_cache_until_the_retry_is_due(setup, monkeypatch):
    import time

    _vault(setup)
    _mode("embeddings")
    index = grounding.scope_index(WHOLE)
    semantic_refresh._FAILED[_token(index)] = (time.monotonic(), index)
    reads = []
    monkeypatch.setattr(embedding_store, "load", lambda keys, real=embedding_store.load: reads.append(1) or real(keys))

    grounding.ground(WHOLE, "carbonara")
    assert reads == []

    monkeypatch.setattr(semantic_refresh, "_RETRY_AFTER_SECONDS", 0.0)
    grounding.ground(WHOLE, "carbonara")
    assert reads != []


def test_after_the_embedding_model_fails_turns_stop_trying_it_for_a_while(setup, monkeypatch):
    _vault(setup)
    _mode("embeddings")
    attempts = []

    def hang(texts, kind, model_name=None):
        attempts.append(kind)
        raise embeddings.EmbeddingUnavailable("timed out")

    monkeypatch.setattr(embeddings, "embed", hang)

    first = grounding.ground(WHOLE, "carbonara")
    for _ in range(3):
        grounding.ground(WHOLE, "carbonara")

    assert len(attempts) == 1 and [h["rel_path"] for h in first] == ["Carbonara.md"]


def test_the_cooldown_covers_the_library_too_and_ends(setup, monkeypatch):
    _vault(setup)
    _mode("embeddings")
    attempts = []

    def hang(texts, kind, model_name=None):
        attempts.append(kind)
        raise embeddings.EmbeddingUnavailable("timed out")

    monkeypatch.setattr(embeddings, "embed", hang)
    grounding.ground(LIBRARY, "carbonara")
    reference.ground(LIBRARY, "carbonara")

    assert len(attempts) == 1  # the library was not tried after the vault failed

    semantic._UNAVAILABLE_UNTIL.clear()  # the time is up
    grounding.ground(LIBRARY, "carbonara")

    assert len(attempts) == 2


def test_the_cooldown_belongs_to_the_model_that_failed(setup, monkeypatch, calls):
    _vault(setup)
    _mode("embeddings")
    semantic._UNAVAILABLE_UNTIL["ollama/nomic-embed-text"] = float("inf")

    assert grounding.ground(WHOLE, "what storage engine did we pick?") == []
    settings_store.set("embedding_model", "ollama/another")

    assert [h["rel_path"] for h in grounding.ground(WHOLE, "what storage engine did we pick?")] == ["Atlas.md"]


def test_the_vault_and_the_library_share_one_embedding_of_the_message(setup, calls):
    _vault(setup)
    _mode("embeddings")

    grounding.ground(LIBRARY, "how do I add another vault?")
    reference.ground(LIBRARY, "how do I add another vault?")
    queries = [texts for kind, texts in calls["embed"] if kind == "query"]
    assert queries == [["how do I add another vault?"]]

    grounding.ground(LIBRARY, "a different message")
    assert len([1 for kind, _ in calls["embed"] if kind == "query"]) == 2


def test_only_the_last_few_message_vectors_are_kept(setup):
    _vault(setup)
    _mode("embeddings")

    for i in range(7):
        grounding.ground(WHOLE, f"message number {i}")

    assert len(semantic._QUERIES) == 4


def test_a_failing_model_is_the_one_that_is_cooled_down_not_the_default(setup, monkeypatch, calls):
    _vault(setup)
    _mode("embeddings")
    settings_store.set("embedding_model", "ollama/failing")

    def embed(texts, kind, model_name=None):
        if model_name == "ollama/failing":
            raise embeddings.EmbeddingUnavailable("no such model")
        return [_vector(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed", embed)
    grounding.ground(WHOLE, "what storage engine did we pick?")
    assert set(semantic._UNAVAILABLE_UNTIL) == {"ollama/failing"}

    settings_store.set("embedding_model", "ollama/nomic-embed-text")

    assert [h["rel_path"] for h in grounding.ground(WHOLE, "what storage engine did we pick?")] == ["Atlas.md"]


# -- found in the review of search and meaning (wave D of the cleanup) -----------------


def test_a_cut_short_cached_vector_is_embedded_again_and_does_not_fail_the_turn(setup, calls, monkeypatch):
    _vault(setup)
    _mode("embeddings")
    first = embedding_store.load  # the real one: read what a first search saved

    grounding.ground(WHOLE, "what storage engine did we pick?")  # fills the cache
    semantic._forget_for_tests()
    calls["embed"].clear()

    def truncated(keys):
        found = first(keys)
        return {k: v[:-1] if i == 0 else v for i, (k, v) in enumerate(found.items())}

    monkeypatch.setattr(embedding_store, "load", truncated)
    hits = grounding.ground(WHOLE, "what storage engine did we pick?")  # must not raise

    documents = [texts for kind, texts in calls["embed"] if kind == "document"]
    assert [len(texts) for texts in documents] == [1]  # only the damaged one, not the whole vault
    assert [h["rel_path"] for h in hits] == ["Atlas.md"]


def test_an_index_with_no_passages_does_not_embed_the_message(setup, calls):
    _mode("embeddings")
    empty = semantic.Index(passages=[], note_df={}, note_count=0, avg_length=0.0)

    assert semantic.refine(empty, "what storage engine did we pick?", []) == []
    assert calls["embed"] == []
