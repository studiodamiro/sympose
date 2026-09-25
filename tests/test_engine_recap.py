"""Recaps of earlier conversations (docs/decisions/023): which sessions get one,
what the model is asked, what is kept, and what is read back. The model is a
stub here; what the real one writes is checked by `live_prompt_cases.py`."""

import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import budget, prompt, recap, recap_refresh, session
from sympose.engine.model import EngineModelError, ModelReply, ReplyLimitError

NEW = "20260924T090000-aaaaaaaa"
OLD = "20260923T090000-bbbbbbbb"
OLDER = "20260922T090000-cccccccc"
OLDEST = "20260921T090000-dddddddd"
LATER = datetime.now(timezone.utc) + timedelta(hours=2)  # every session written now is long finished by then


@pytest.fixture(autouse=True)
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(budget, "_native_max", lambda model: 8192)
    monkeypatch.setattr(recap_refresh, "_CANNOT_RECAP", set())
    monkeypatch.setattr(recap_refresh, "_RUNNING", {})
    return base


class Asked(list):
    """The calls made to the model, and the replies it gives in turn (the last repeats)."""

    def __init__(self):
        super().__init__()
        self.replies: list = [ModelReply("They planned the Atlas database.", 5)]


@pytest.fixture
def asked(monkeypatch):
    calls = Asked()

    def call_model(messages, model=None, **limits):
        calls.append({"messages": messages, "model": model, **limits})
        reply = calls.replies[min(len(calls), len(calls.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(recap_refresh.model_mod, "call_model", call_model)
    return calls


def say(session_id: str, *pairs: tuple[str, str], handle: str = "samantha") -> None:
    for user, assistant in pairs:
        session.append_turn(handle, session_id, user, assistant)


def talk(session_id: str, turns: int = 2, handle: str = "samantha") -> None:
    say(session_id, *[(f"question {i} about Atlas", f"answer {i}") for i in range(turns)], handle=handle)


def recap_file(session_id: str, handle: str = "samantha") -> str:
    with open(os.path.join(session.recaps_dir(handle), f"{session_id}.md"), encoding="utf-8") as f:
        return f.read()


def has_recap(session_id: str, handle: str = "samantha") -> bool:
    return os.path.exists(os.path.join(session.recaps_dir(handle), f"{session_id}.md"))


# -- which sessions get a recap --


def test_a_finished_session_gets_a_recap_beside_its_sessions(asked):
    talk(NEW)

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\nThey planned the Atlas database.\n"
    assert os.path.dirname(session.recaps_dir("samantha")) == os.path.dirname(session.sessions_dir("samantha"))
    assert len(asked) == 1


def test_the_model_is_given_the_recap_instructions_and_only_what_the_user_wrote(asked):
    say(NEW, ("which database for Atlas?", "SQLite, said the note."), ("why?" + " x" * 600, "It is simple."))

    recap_refresh.refresh("samantha", now=LATER)

    system, user = asked[0]["messages"]
    assert system == {"role": "system", "content": prompt.RECAP_INSTRUCTIONS}
    assert user["content"].startswith("Conversation:\nUser: which database for Atlas?\nUser: why? x x")
    assert user["content"].endswith("\n\nRecap:")
    assert "SQLite" not in user["content"] and "simple" not in user["content"]  # the persona's replies stay out
    long_line = user["content"].splitlines()[2]
    assert len(long_line) == len("User: ") + 1000  # a very long message is cut


def test_it_asks_the_personas_own_model_in_its_window_with_a_short_reply_limit(asked, profiles):
    write_persona(profiles, "ada", "name: Ada\nvault_folders: '*'\nmodel: 'ollama_chat/other:1b'\n")
    talk(NEW, handle="ada")

    recap_refresh.refresh("ada", now=LATER)

    assert asked[0]["model"] == "ollama_chat/other:1b"
    assert asked[0]["num_ctx"] == 8192 and asked[0]["max_tokens"] == 200


def test_a_session_with_one_turn_gets_no_recap(asked):
    talk(NEW, turns=1)

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == [] and not has_recap(NEW)


def test_a_session_touched_in_the_last_half_hour_may_still_be_running_and_is_left(asked):
    talk(NEW)
    updated = datetime.fromisoformat(session.load_session("samantha", NEW)["meta"]["updated_at"])

    recap_refresh.refresh("samantha", now=updated + timedelta(minutes=29, seconds=59))
    assert asked == []

    recap_refresh.refresh("samantha", now=updated + timedelta(minutes=30))
    assert len(asked) == 1


def test_a_very_long_session_is_recapped_from_its_last_forty_turns(asked, monkeypatch):
    say(NEW, *[(f"turn{i:03d} about Atlas", "ok") for i in range(50)])
    monkeypatch.setattr(budget, "budget_for", lambda model: None)  # no window trimming: only the cap acts

    recap_refresh.refresh("samantha", now=LATER)

    sent = asked[0]["messages"][1]["content"]
    assert sent.count("User:") == 40 and "turn009" not in sent and "turn010" in sent and "turn049" in sent
    assert recap_file(NEW).startswith("<!-- turns: 50 -->")  # the header still counts the whole session


def test_a_session_stamp_without_a_time_zone_is_read_as_utc(asked):
    talk(NEW)
    path = session.session_path("samantha", NEW)
    lines = open(path, encoding="utf-8").read().splitlines()
    meta = __import__("json").loads(lines[0])
    meta["updated_at"] = "2026-09-24T09:00:00"
    lines[0] = __import__("json").dumps(meta)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1


def test_only_the_three_newest_sessions_are_considered(asked):
    for sid in (OLDEST, OLDER, OLD, NEW):
        talk(sid)

    recap_refresh.refresh("samantha", now=LATER)

    assert [has_recap(s) for s in (NEW, OLD, OLDER, OLDEST)] == [True, True, True, False]


def test_a_session_that_already_has_a_recap_is_not_written_again(asked):
    talk(NEW)
    recap_refresh.refresh("samantha", now=LATER)
    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1


def test_a_session_resumed_after_its_recap_gets_a_fresh_one(asked):
    talk(NEW, turns=2)
    recap_refresh.refresh("samantha", now=LATER)
    say(NEW, ("one more thing", "noted"))
    asked.replies[:] = [ModelReply("Now with a third turn.", 5)]

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 3 -->\nNow with a third turn.\n"


def test_a_recap_the_user_edited_and_left_without_its_header_is_never_rewritten(asked):
    talk(NEW)
    os.makedirs(session.recaps_dir("samantha"))
    with open(os.path.join(session.recaps_dir("samantha"), f"{NEW}.md"), "w", encoding="utf-8") as f:
        f.write("My own words about that day.\n")

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == [] and recap_file(NEW) == "My own words about that day.\n"


def test_an_emptied_file_stays_empty_so_a_recap_can_be_stopped(asked):
    talk(NEW)
    os.makedirs(session.recaps_dir("samantha"))
    open(os.path.join(session.recaps_dir("samantha"), f"{NEW}.md"), "w").close()

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == [] and recap_file(NEW) == ""


def test_a_deleted_recap_is_written_again(asked):
    talk(NEW)
    recap_refresh.refresh("samantha", now=LATER)
    os.remove(os.path.join(session.recaps_dir("samantha"), f"{NEW}.md"))

    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 2 and has_recap(NEW)


def test_a_conversation_with_nothing_to_carry_over_is_marked_and_not_asked_again(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("NONE", 5)]

    recap_refresh.refresh("samantha", now=LATER)
    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\n"
    assert len(asked) == 1
    assert recap.latest("samantha") == []


@pytest.mark.parametrize("said", ["none", "None.", " NONE\n"])
def test_the_no_recap_answer_is_recognised_however_it_is_dressed(asked, said):
    talk(NEW)
    asked.replies[:] = [ModelReply(said, 5)]

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\n"


def test_a_persona_that_does_not_exist_writes_nothing(asked):
    recap_refresh.refresh("nobody", now=LATER)

    assert asked == []


def test_the_knob_turns_writing_and_reading_off(asked):
    talk(NEW)
    settings_store.set("session_recaps", False)

    recap_refresh.refresh("samantha", now=LATER)
    assert asked == [] and not has_recap(NEW)

    settings_store.set("session_recaps", True)
    recap_refresh.refresh("samantha", now=LATER)
    settings_store.set("session_recaps", False)
    assert recap.latest("samantha") == []


def test_anything_but_an_explicit_false_leaves_recaps_on():
    for value in (None, True, "off", 0):
        settings_store.set("session_recaps", value)
        assert recap.enabled(), value


# -- what the model may get wrong or fail at --


def test_a_failed_model_call_stops_the_run_and_the_sessions_are_tried_again_next_time(asked):
    talk(NEW)
    talk(OLD)
    asked.replies[:] = [EngineModelError("down")]

    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1 and not has_recap(NEW) and not has_recap(OLD)


def test_a_model_that_cannot_write_in_the_reply_limit_is_not_asked_again(asked):
    talk(NEW)
    asked.replies[:] = [ReplyLimitError("thinking")]

    recap_refresh.refresh("samantha", now=LATER)
    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1 and not has_recap(NEW)


def test_a_reply_cut_off_at_the_limit_is_kept_up_to_its_last_whole_sentence(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("They chose SQLite. They still had to decide the back", 5, truncated=True)]

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\nThey chose SQLite.\n"


def test_a_reply_cut_off_before_its_first_sentence_ends_is_not_kept(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("They were choosing a data", 5, truncated=True)]

    recap_refresh.refresh("samantha", now=LATER)

    assert not has_recap(NEW)


def test_a_whole_reply_with_no_full_stop_is_kept_as_it_is(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("Working on the Atlas database choice", 5)]  # finished, so not cut off

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\nWorking on the Atlas database choice\n"


def test_a_cut_reply_whose_only_stop_is_its_first_character_is_not_kept(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply(". and then it went on to", 5, truncated=True)]

    recap_refresh.refresh("samantha", now=LATER)

    assert not has_recap(NEW)


def test_a_session_whose_record_has_no_update_time_is_skipped_not_guessed(asked):
    talk(NEW)
    path = session.session_path("samantha", NEW)
    lines = open(path, encoding="utf-8").read().splitlines()
    meta = __import__("json").loads(lines[0])
    del meta["updated_at"]
    lines[0] = __import__("json").dumps(meta)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == [] and not has_recap(NEW)


def test_an_unusable_reply_stops_the_run_so_it_costs_one_call_not_three(asked):
    for sid in (NEW, OLD, OLDER):
        talk(sid)
    asked.replies[:] = [ModelReply("They were choosing a data", 5, truncated=True)]

    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1 and not any(has_recap(s) for s in (NEW, OLD, OLDER))


def test_a_reply_of_only_whitespace_is_not_kept(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("  \n ", 5)]

    recap_refresh.refresh("samantha", now=LATER)

    assert not has_recap(NEW)


def test_whitespace_in_a_recap_is_collapsed_to_single_spaces(asked):
    talk(NEW)
    asked.replies[:] = [ModelReply("They  planned\n\nthe   trip.", 5)]

    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\nThey planned the trip.\n"


def test_only_the_newest_turns_that_fit_the_window_are_sent(asked, monkeypatch):
    say(NEW, *[(f"turn{i} " + "word " * 30, f"reply{i}") for i in range(6)])
    monkeypatch.setattr(budget, "count_tokens", lambda messages, model: sum(len(m["content"].split()) for m in messages))
    monkeypatch.setattr(budget, "budget_for", lambda model: budget.Budget(prompt_tokens=200, num_ctx=1000, reply_cap=100))

    recap_refresh.refresh("samantha", now=LATER)

    sent = asked[0]["messages"][1]["content"]
    assert "turn5" in sent and "turn0" not in sent


def test_when_not_even_one_turn_fits_the_model_is_not_asked(asked, monkeypatch):
    talk(NEW)
    monkeypatch.setattr(budget, "budget_for", lambda model: budget.Budget(prompt_tokens=5, num_ctx=1000, reply_cap=100))

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == [] and not has_recap(NEW)


def test_a_model_with_no_known_window_is_sent_everything(asked, monkeypatch):
    talk(NEW, turns=4)
    monkeypatch.setattr(budget, "budget_for", lambda model: None)

    recap_refresh.refresh("samantha", now=LATER)

    assert asked[0]["num_ctx"] is None and asked[0]["messages"][1]["content"].count("User:") == 4


def test_a_recap_that_cannot_be_saved_does_not_raise(asked, monkeypatch):
    talk(NEW)

    def refuse(*args, **kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(recap, "write", refuse)

    recap_refresh.refresh("samantha", now=LATER)

    assert len(asked) == 1


# -- what is read back --


def put(session_id: str, text: str, handle: str = "samantha", header: bool = True) -> None:
    os.makedirs(session.recaps_dir(handle), exist_ok=True)
    body = f"<!-- turns: 2 -->\n{text}\n" if header else text
    with open(os.path.join(session.recaps_dir(handle), f"{session_id}.md"), "w", encoding="utf-8") as f:
        f.write(body)


def test_latest_gives_the_two_newest_recaps_newest_first_with_the_day_of_each():
    for sid in (OLDER, OLD, NEW):
        talk(sid)
    put(OLDER, "third")
    put(OLD, "second")
    put(NEW, "first")

    assert recap.latest("samantha") == [
        {"session": NEW, "date": "2026-09-24", "text": "first", "last": True},
        {"session": OLD, "date": "2026-09-23", "text": "second", "last": False},
    ]


def test_a_recap_is_not_the_last_conversation_when_a_newer_session_has_none():
    talk(OLD)
    talk(NEW)  # the real last session: nothing to carry over
    put(OLD, "second")
    put(NEW, "")

    assert recap.latest("samantha") == [
        {"session": OLD, "date": "2026-09-23", "text": "second", "last": False}
    ]


def test_the_last_conversation_is_the_newest_session_other_than_the_one_being_run():
    talk(OLD)
    talk(NEW)
    put(OLD, "second")

    assert recap.latest("samantha", exclude=NEW) == [
        {"session": OLD, "date": "2026-09-23", "text": "second", "last": True}
    ]


def test_the_session_being_run_is_never_read_back_into_itself():
    put(OLD, "second")
    put(NEW, "first")

    assert [r["text"] for r in recap.latest("samantha", exclude=NEW)] == ["second"]


def test_a_conversation_marked_as_nothing_to_carry_over_is_skipped_for_the_next_one():
    put(NEW, "")
    put(OLD, "second")
    put(OLDER, "third")

    assert [r["text"] for r in recap.latest("samantha")] == ["second", "third"]


def test_a_file_the_user_wrote_without_a_header_is_read_as_it_is():
    put(NEW, "My own words.", header=False)

    assert [(r["date"], r["text"]) for r in recap.latest("samantha")] == [("2026-09-24", "My own words.")]


def test_a_recap_is_cut_to_a_size_the_prompt_can_carry():
    put(NEW, "x" * 5000)

    assert len(recap.latest("samantha")[0]["text"]) == 800


def test_without_a_recaps_folder_or_with_other_files_there_is_nothing_to_read():
    assert recap.latest("samantha") == []
    os.makedirs(session.recaps_dir("samantha"))
    open(os.path.join(session.recaps_dir("samantha"), "notes.txt"), "w").close()
    assert recap.latest("samantha") == []


def test_recaps_are_kept_apart_per_persona(profiles):
    write_persona(profiles, "ada", "name: Ada\nvault_folders: '*'\n")
    put(NEW, "Samantha's", handle="samantha")
    put(OLD, "Ada's", handle="ada")

    assert [r["text"] for r in recap.latest("ada")] == ["Ada's"]


# -- in the background --


def test_the_refresh_runs_on_its_own_thread_and_a_second_call_meanwhile_is_refused(monkeypatch):
    started, release = threading.Event(), threading.Event()
    seen: list[str] = []

    def slow_refresh(handle):
        seen.append(threading.current_thread().name)
        started.set()
        release.wait(5)

    monkeypatch.setattr(recap_refresh, "refresh", slow_refresh)

    assert recap_refresh.refresh_in_background("samantha") is True
    assert started.wait(5)
    assert recap_refresh.refresh_in_background("samantha") is False
    assert recap_refresh.refresh_in_background("ada") is True  # another persona is its own run
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("recaps-"):
            thread.join(5)

    assert recap_refresh.refresh_in_background("samantha") is True  # finished, so it may run again
    for thread in threading.enumerate():
        if thread.name.startswith("recaps-"):
            thread.join(5)
    assert seen[0] == "recaps-samantha" and threading.current_thread().name not in seen


def test_a_failure_on_the_thread_is_logged_not_raised_and_the_handle_is_freed(monkeypatch, caplog):
    def boom(handle):
        raise RuntimeError("broken")

    monkeypatch.setattr(recap_refresh, "refresh", boom)

    recap_refresh.refresh_in_background("samantha")
    for thread in threading.enumerate():
        if thread.name.startswith("recaps-"):
            thread.join(5)

    assert "Recap refresh for samantha failed: broken" in caplog.text
    assert recap_refresh.refresh_in_background("samantha") is True
    for thread in threading.enumerate():
        if thread.name.startswith("recaps-"):
            thread.join(5)


def test_the_thread_is_a_daemon_so_quitting_never_waits_for_a_model_call(monkeypatch):
    release = threading.Event()
    flags: list[bool] = []

    def wait(handle):
        flags.append(threading.current_thread().daemon)
        release.wait(5)

    monkeypatch.setattr(recap_refresh, "refresh", wait)
    recap_refresh.refresh_in_background("samantha")
    for _ in range(100):
        if flags:
            break
        threading.Event().wait(0.05)
    release.set()

    assert flags == [True]


def test_a_turn_can_wait_for_a_refresh_still_running_and_gives_up_after_the_timeout(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(recap_refresh, "refresh", lambda handle: release.wait(5))

    assert recap_refresh.wait_for_refresh("samantha", timeout=0) is True  # none running: nothing to wait for
    recap_refresh.refresh_in_background("samantha")
    assert recap_refresh.wait_for_refresh("samantha", timeout=0.05) is False  # still going after the timeout
    assert recap_refresh.wait_for_refresh("ada", timeout=0.05) is True  # another persona's run is not this one's
    release.set()
    assert recap_refresh.wait_for_refresh("samantha", timeout=5) is True
    assert recap_refresh.refresh_in_background("samantha") is True  # finished, so it may run again
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("recaps-"):
            thread.join(5)


def test_the_default_wait_is_short_enough_that_a_stuck_call_cannot_hold_a_turn_long():
    assert 0 < recap_refresh._WAIT_SECONDS <= 30


def test_the_engine_hands_channels_the_background_refresh_not_the_blocking_one():
    from sympose import engine

    assert engine.refresh_recaps is recap_refresh.refresh_in_background


def test_a_recap_saved_in_another_encoding_is_skipped_not_a_failed_turn():
    os.makedirs(session.recaps_dir("samantha"))
    with open(os.path.join(session.recaps_dir("samantha"), f"{NEW}.md"), "wb") as f:
        f.write("caf\u00e9 notes".encode("latin-1"))
    put(OLD, "second")

    assert [r["text"] for r in recap.latest("samantha")] == ["second"]


def test_a_recap_is_written_whole_with_no_temporary_file_left_behind(asked):
    talk(NEW)

    recap_refresh.refresh("samantha", now=LATER)

    assert os.listdir(session.recaps_dir("samantha")) == [f"{NEW}.md"]


def test_an_interrupted_write_leaves_the_earlier_recap_as_it_was(asked, monkeypatch):
    talk(NEW)
    put(NEW, "The earlier recap.")
    say(NEW, ("one more", "ok"))  # now stale: covers 2 turns of 3

    def die(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(recap.os, "replace", die)
    recap_refresh.refresh("samantha", now=LATER)

    assert recap_file(NEW) == "<!-- turns: 2 -->\nThe earlier recap.\n"
    assert os.listdir(session.recaps_dir("samantha")) == [f"{NEW}.md"]  # and no half-written file is left


def test_two_writers_do_not_share_a_temporary_file(monkeypatch):
    sources = []
    real_replace = os.replace

    def spy(src, dst):
        sources.append(src)
        real_replace(src, dst)

    monkeypatch.setattr(recap.os, "replace", spy)
    recap.write("samantha", NEW, 2, "first")
    recap.write("samantha", NEW, 2, "second")

    assert len(set(sources)) == 2 and all(not s.endswith(f"{NEW}.md.tmp") for s in sources)
    assert recap_file(NEW) == "<!-- turns: 2 -->\nsecond\n"


def test_throwaway_sessions_do_not_starve_a_real_one_of_its_recap(asked):
    talk(OLDER)  # the real one
    for sid in (OLD, "20260924T080000-eeeeeeee", NEW):
        talk(sid, turns=1)

    recap_refresh.refresh("samantha", now=LATER)

    assert has_recap(OLDER) and not any(has_recap(s) for s in (OLD, NEW))


def test_only_the_newest_ten_sessions_are_looked_at_and_three_recapped(asked):
    ids = [f"202609{day:02d}T090000-aaaaaaaa" for day in range(1, 14)]
    for sid in ids:
        talk(sid)

    recap_refresh.refresh("samantha", now=LATER)

    assert [has_recap(s) for s in reversed(ids)][:3] == [True, True, True]
    assert sum(has_recap(s) for s in ids) == 3


def test_a_real_session_behind_nine_throwaways_is_still_reached(asked):
    talk("20260901T090000-aaaaaaaa")
    for day in range(2, 11):
        talk(f"202609{day:02d}T090000-aaaaaaaa", turns=1)

    recap_refresh.refresh("samantha", now=LATER)

    assert has_recap("20260901T090000-aaaaaaaa")  # the tenth newest


def test_a_real_session_behind_ten_throwaways_is_not_looked_for(asked):
    talk("20260901T090000-aaaaaaaa")
    for day in range(2, 12):
        talk(f"202609{day:02d}T090000-aaaaaaaa", turns=1)

    recap_refresh.refresh("samantha", now=LATER)

    assert asked == []  # the eleventh newest is past the scan


def test_a_cloud_model_gets_room_to_think_for_the_recap(asked, profiles):
    write_persona(profiles, "ada", "name: Ada\nvault_folders: '*'\nmodel: 'gemini/gemini-flash-latest'\n")
    talk(NEW, handle="ada")

    recap_refresh.refresh("ada", now=LATER)

    assert asked[0]["model"] == "gemini/gemini-flash-latest"
    assert asked[0]["max_tokens"] == 4000
