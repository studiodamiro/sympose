"""The labelled messages of the retrieval comparison (docs/decisions/027), on the synthetic vault
`tests/fixtures/retrieval_vault`: a copy of the grounding vault plus notes that share ordinary
words with Sympose topics ("Model Railway", "Vault Security Policy", "Employee Profiles") and a few
notes about Sympose itself. Nothing here is anyone's own data.

lib:   True  -> the Sympose library must attach at least one passage (and `lib_note`, if set, must be among them)
       False -> the library must attach nothing
       None  -> either is fine
need:  vault notes that must attach
ok:    vault notes that are acceptable but not required (anything else attached is junk)
split: the messages alternate between "dev" (where thresholds were chosen) and "test" (held out)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Msg:
    id: str
    cat: str
    text: str
    lib: bool | None = False
    lib_note: str | None = None
    need: tuple[str, ...] = ()
    ok: tuple[str, ...] = ()
    split: str = "dev"


ATLAS = "Projects/Atlas.md"
EMP = "Work/Employee Profiles.md"
DB = "Work/Database Schema.md"
VAULTSEC = "Work/Vault Security Policy.md"
RAIL = "Hobbies/Model Railway.md"
ROUTER = "Home/Router Settings.md"
BAND = "Music/Band Practice Sessions.md"
ROADMAP = "Projects/Sympose/Sympose Roadmap.md"
PERSONA_IDEAS = "Projects/Sympose/Persona Ideas.md"

_RAW = [
    # --- how Sympose works: the library answers, the vault has nothing to add ---
    ("sympose", "can you create a new profile for me?", True, "Personas.md"),
    ("sympose", "how do I add another vault?", True, "Add or switch vaults.md"),
    ("sympose", "how do I switch models?", True, "Choosing a model.md"),
    ("sympose", "where are my settings stored?", True, "Settings.md"),
    ("sympose", "can you review our session logs?", True, None),
    ("sympose", "how do I make a new agent?", True, "Personas.md"),
    ("sympose", "what does the context meter show?", True, "The context meter.md"),
    ("sympose", "what commands can I use in the chat?", True, "Chat commands.md"),
    ("sympose", "is my data sent anywhere?", True, "Privacy and data.md"),
    ("sympose", "can you create a note in my vault?", True, "Not built yet.md"),
    ("sympose", "how do I change which persona I talk to?", True, None),
    ("sympose", "what model are you running on?", True, None),
    ("sympose", "why is the reply so slow?", True, "Troubleshooting.md"),
    ("sympose", "what is Sympose?", True, "What is Sympose.md"),
    ("sympose", "who made Sympose?", True, "History and author.md"),
    ("sympose", "can I use a cloud model?", True, "Choosing a model.md"),
    ("sympose", "how do I change your name?", True, None),
    ("sympose", "how do I set up a new vault?", True, "Add or switch vaults.md"),
    ("sympose", "can you show me the settings for the model?", True, None),
    ("sympose", "how do you use my notes?", True, "How Samantha uses your notes.md"),
]

_VAULT = [
    # --- the user's own notes: the vault answers ---
    ("vault", "what did we decide about the database for Atlas?", ATLAS),
    ("vault", "how long do I bake the sourdough?", "Recipes/Sourdough.md"),
    ("vault", "what goes in a carbonara? I only remember guanciale", "Recipes/Pasta Carbonara.md"),
    ("vault", "what's my training plan?", "Health/Fitness Plan.md"),
    ("vault", "what are the four rules of deep work?", "Reading/Deep Work.md"),
    ("vault", "explain tacking and jibing", "Reading/Sailing Basics.md"),
    ("vault", "how did we go over budget?", "Work/Budget.md"),
    ("vault", "when are the Lisbon flights?", "Travel/Lisbon Trip.md"),
    ("vault", "who is Priya?", "Work/Meeting 2026-09-18.md"),
    ("vault", "why is it called Atlas?", "Ideas/Atlas Naming.md"),
    ("vault", "what storage engine did we pick?", ATLAS),
    ("vault", "what did I write about keeping bread starter alive?", "Recipes/Sourdough.md"),
    # --- vault notes that share ordinary words with Sympose topics ---
    ("clash", "what is in my employee profiles note?", EMP),
    ("clash", "what did we decide about the database schema?", DB),
    ("clash", "remind me of the vault rotation policy", VAULTSEC),
    ("clash", "what are the settings on my router?", ROUTER),
    ("clash", "when is band practice?", BAND),
    ("clash", "how many wagons on my model railway?", RAIL),
    ("clash", "how do I change the wifi name?", ROUTER),
]

_MIXED = [
    # --- the user's own notes about Sympose: the vault answers (the library may add) ---
    ("mixed", "what did I write in my Sympose roadmap?", ROADMAP),
    ("mixed", "what persona ideas did I write down?", PERSONA_IDEAS),
    ("mixed", "what are my plans for embeddings in Sympose?", ROADMAP),
]

_NONE = [
    # --- general knowledge and chat: nothing should attach ---
    ("general", "who wrote Pride and Prejudice?"),
    ("general", "give me names of famous female computer scientists from history"),
    ("general", "what is the capital of Portugal?"),
    ("general", "explain what an embedding is"),
    ("general", "suggest a name for my new puppy"),
    ("general", "what is the tallest mountain in the world?"),
    ("general", "write me a haiku about autumn"),
    ("general", "I need a new name for my new project, something to do over the next few weeks"),
    ("general", "can you name some famous explorers from history?"),
    ("chat", "hey sam, are you here?"),
    ("chat", "thanks, that helps!"),
    ("chat", "how are you today?"),
    ("chat", "are you ok?"),
    ("chat", "hey"),
    ("chat", "good morning"),
    ("chat", "I'm tired today"),
    ("chat", "ok great, let's continue"),
]


def _build() -> list[Msg]:
    out: list[Msg] = []
    for cat, text, lib, note in _RAW:
        out.append(Msg(f"{cat}-{len(out)}", cat, text, lib=lib, lib_note=note))
    for cat, text, need in _VAULT:
        out.append(Msg(f"{cat}-{len(out)}", cat, text, lib=False, need=(need,)))
    for cat, text, need in _MIXED:
        out.append(Msg(f"{cat}-{len(out)}", cat, text, lib=None, need=(need,)))
    for cat, text in _NONE:
        out.append(Msg(f"{cat}-{len(out)}", cat, text, lib=False))
    # alternate dev / test within each category so both halves see every kind of message
    seen: dict[str, int] = {}
    final = []
    for m in out:
        n = seen.get(m.cat, 0)
        seen[m.cat] = n + 1
        final.append(Msg(**{**m.__dict__, "split": "dev" if n % 2 == 0 else "test"}))
    return final


_OK = {
    "why is it called Atlas?": (ATLAS,),
    "what did we decide about the database for Atlas?": ("Ideas/Atlas Naming.md",),
    "what is Sympose?": (ROADMAP, PERSONA_IDEAS),
    "who made Sympose?": (ROADMAP, PERSONA_IDEAS),
}
MESSAGES = [Msg(**{**m.__dict__, "ok": _OK.get(m.text, m.ok)}) for m in _build()]

# Notes with no body text (docs/decisions/030): a card of properties, quotes titled by the quote, an outline,
# a date-titled note. Kept apart from MESSAGES so that set stays comparable with the numbers in ADR 027; the
# notes are in the same vault, so MESSAGES also shows whether they attach where they should not.
_NO_BODY = [
    ("title", "which quote says done is better than perfect?", "Quotes/Done is better than perfect.md"),
    ("title", "do I have a note about slow is smooth and smooth is fast?", "Quotes/Slow is smooth and smooth is fast.md"),
    ("title", "what did I write on 2026-09-22?", "Journal/2026-09-22.md"),
    ("card", "who is Anna Ruiz?", "People/Anna Ruiz.md"),
    ("card", "tell me about Annie", "People/Anna Ruiz.md"),
    ("card", "what does Marc do?", "People/Marcus Webb.md"),
    ("card", "what is Marcus Webb's role?", "People/Marcus Webb.md"),
    ("outline", "what chargers and adapters do I need to pack?", "Travel/Packing Outline.md"),
    ("outline", "do I have an outline for what to pack?", "Travel/Packing Outline.md"),
]
_NO_BODY_NONE = [
    ("nothing", "I feel slow this morning"),
    ("nothing", "good, I'm done for today"),
    ("nothing", "what is the capital of Portugal?"),
    ("nothing", "how are you today?"),
]
NO_BODY_MESSAGES = [
    Msg(f"{cat}-{n}", cat, text, lib=None, need=(need,), ok=("Travel/Lisbon Trip.md",) if cat == "outline" else (), split="dev" if n % 2 == 0 else "test")
    for n, (cat, text, need) in enumerate(_NO_BODY)
] + [
    Msg(f"{cat}-{n}", cat, text, lib=False, split="dev" if n % 2 == 0 else "test")
    for n, (cat, text) in enumerate(_NO_BODY_NONE, start=len(_NO_BODY))
]
