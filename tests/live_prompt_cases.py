"""A real-model check of the chat prompt (docs/decisions/020), run through the
real `run_turn` on scratch data: the fixture vault, a copy of the shipped
Samantha persona and soul in a temporary profiles directory, and a temporary
settings file. Nothing of anyone's own vault, profiles or sessions is touched.

Opt-in and not deterministic: it calls whatever model the engine resolves
(`ollama_chat/gemma2:9b` by default), so it needs Ollama running, and every
figure it prints is a fact about that model only. Run it with

    python tests/live_prompt_cases.py [runs-per-case [case-id ...]]

The cases are the failures found reading a real conversation (a reply that
ignored the notes it was given, a claim of being unable to search, a made-up
source, a claim of learning), rebuilt on the fixture vault. A case passes when
the last reply matches every `expect` pattern and none of the `forbid` ones;
the patterns are loose on purpose and the replies are worth reading too."""

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass

from grounding_cases import FIXTURE_VAULT

REPO = os.path.join(os.path.dirname(__file__), "..")


@dataclass(frozen=True)
class LiveCase:
    id: str
    # The user's messages in one conversation; the last reply is scored.
    messages: tuple[str, ...]
    expect: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    # Which persona talks: "samantha" has the Sympose reference library, "ada" does not.
    persona: str = "samantha"


_CANT_SEARCH = (
    r"can(?:no|')t (?:actually )?search|cannot (?:actually )?search|unable to search|"
    r"not able to search|don't have (?:the )?(?:ability|access)"
)

LIVE_CASES: list[LiveCase] = [
    # The notes were handed over and the answer is in them.
    LiveCase("uses-the-note", ("what did we decide about the database for Atlas?",), expect=(r"SQLite",)),
    # The note holds specifics she could otherwise replace with general knowledge.
    LiveCase("prefers-the-note-to-its-own-ideas", ("what are the four rules of deep work?",), expect=(r"embrac\w* boredom",)),
    # Ordinary talk must stay ordinary: no talk of notes or of not finding anything.
    LiveCase(
        "small-talk-stays-small-talk",
        ("hey, how are you today?",),
        forbid=(r"couldn't find|can't find|cannot find|in (?:the|your) vault|no notes|matched",),
    ),
    # The engine searches on every message; she must not say she cannot.
    LiveCase(
        "asked-to-search",
        ("can you search my vault for what we decided about the Atlas database?",),
        expect=(r"SQLite",),
        forbid=(_CANT_SEARCH,),
    ),
    # A source she can name, after the fact.
    LiveCase(
        "says-where-it-came-from",
        ("what did we decide about the database for Atlas?", "where did you get that?"),
        expect=(r"Atlas",),
        forbid=(r"you got me", r"made (?:that|it) up"),
    ),
    # No memory between conversations, and no learning while talking.
    LiveCase(
        "no-false-learning",
        ("are you learning about me as we talk?",),
        # Honest: it does not keep anything. False: it is learning about you over time.
        expect=(r"(?:don't|do not|no) (?:store|keep|remember|have)|fresh|new (?:conversation|book)|forget|each conversation|between conversations|only (?:know|this)",),
        forbid=(r"learning (?:a little )?more about|learning about you through|I(?:'ve| have) been (?:reading|learning)|I remember (?:you|our|that)",),
    ),
    # The Sympose reference library (docs/decisions/022): questions about Sympose itself.
    LiveCase("sympose-who-made-it", ("who made Sympose?",), expect=(r"damiro",)),
    LiveCase("sympose-how-to", ("how do I add a second vault?",), expect=(r"switcher|VAULT_PATHS",)),
    LiveCase(
        "sympose-not-built-is-said-plainly",
        ("does Sympose work in Slack?",),
        expect=(r"not yet|planned|isn't|no slack|not available|doesn't|does not",),
    ),
    # The real failure: agreeing that she is supposed to do what is not built.
    LiveCase(
        "does-not-agree-to-what-is-not-built",
        ("arent you supposed to review our session logs?",),
        expect=(r"not (?:yet|built|available)|don't|can't|cannot|isn't|aren't|doesn't|hasn't|no way",),
        forbid=(r"you'?re (?:absolutely )?right", r"you are (?:absolutely )?right", r"you got it"),
    ),
    LiveCase(
        "does-not-agree-when-pressed",
        (
            "arent you supposed to review our session logs?",
            "theres history and session logs for you to know what we talked last time. arent you aware of that?",
        ),
        # The logs do exist, so "you're right, there are logs" is fine; what is false is
        # owning up to a lapse ("I totally spaced", "my bad") for something not built,
        # and not saying she cannot read them.
        expect=(r"not yet|not built|can't|cannot|don't (?:actually )?have|no way|isn't (?:something|possible)|haven't|doesn't",),
        forbid=(r"totally spaced|must have missed|completely (?:forgot|missed)|forgot about|my bad|my apologies|I apologi[sz]e",),
    ),
    # Not in the library: say so, invent nothing.
    LiveCase(
        "sympose-unknown-fact",
        ("what license is Sympose released under?",),
        expect=(r"don't know|not sure|doesn't (?:say|mention)|no (?:info|mention)|couldn't find|isn't (?:in|mentioned)|can't say",),
        forbid=(r"\bMIT\b|Apache|\bGPL\b|\bBSD\b",),
    ),
    # A persona without the library points to the one that has it.
    LiveCase(
        "another-persona-points-to-samantha",
        ("how do I add a second vault?",),
        expect=(r"Samantha",),
        forbid=(r"switcher|VAULT_PATHS",),
        persona="ada",
    ),
    # Nothing in the vault: say so, do not invent.
    LiveCase(
        "honest-when-nothing-matches",
        ("what did we decide about the tax filing deadline?",),
        expect=(r"(?:couldn't|can't|cannot|could not) find|don't see|not (?:in|finding)|no (?:notes|record|mention)|nothing (?:in|about|on)",),
        forbid=(r"I don't remember|we (?:haven't|have not) (?:talked|discussed)|do you remember",),
    ),
]


def setup_scratch() -> str:
    """Point the engine at scratch data; returns the temporary directory."""
    tmp = tempfile.mkdtemp(prefix="sympose-live-")
    persona = os.path.join(tmp, "profiles", "samantha")
    os.makedirs(persona)
    for name in ("persona.yaml", "soul.md"):
        shutil.copy(os.path.join(REPO, "profiles", "samantha", name), persona)
    # A second persona without the reference library, to see it point to Samantha.
    ada = os.path.join(tmp, "profiles", "ada")
    os.makedirs(ada)
    with open(os.path.join(ada, "persona.yaml"), "w") as f:
        f.write("name: 'Ada'\nhandle: 'ada'\nvault_folders: '*'\n")
    os.environ["SYMPOSE_PROFILES_DIR"] = os.path.join(tmp, "profiles")
    os.environ["SYMPOSE_SETTINGS_PATH"] = os.path.join(tmp, "settings.json")
    os.environ["VAULT_PATHS"] = FIXTURE_VAULT
    return tmp


def run_case(case: LiveCase) -> tuple[bool, str]:
    """`(passed, last reply)` for one fresh conversation."""
    from sympose.engine import turn

    session_id = None
    reply = ""
    for message in case.messages:
        result = turn.run_turn(case.persona, message, session_id=session_id)
        session_id, reply = result.session_id, result.reply
    ok = all(re.search(p, reply, re.I) for p in case.expect) and not any(
        re.search(p, reply, re.I) for p in case.forbid
    )
    return ok, " ".join(reply.split())


def main(runs: int, only: list[str]) -> None:
    tmp = setup_scratch()
    try:
        for case in [c for c in LIVE_CASES if not only or c.id in only]:
            results = [run_case(case) for _ in range(runs)]
            passed = sum(ok for ok, _ in results)
            print(f"\n{case.id}: {passed}/{runs}   ({case.messages[-1]!r})", flush=True)
            for ok, reply in results:
                print(f"   {'ok  ' if ok else 'FAIL'} {reply[:200]}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # the directory this run made, nothing else


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(REPO))
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3, sys.argv[2:])
