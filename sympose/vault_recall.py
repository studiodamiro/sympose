"""
Conversational-recall subject extraction: turning a natural request like
"pull up my notes on grief" or "what did I write about Rilke" into a clean
search term, and detecting whether a message is itself a fresh recall
request at all.

`resolve_turn_context` — the orchestrator that ties this together with
nearly every other vault capability (search, backlinks, folder discovery,
the manifest digest, chronological sampling) to answer a turn from real
vault content, or not at all — originally stayed a VaultManager method
directly in vault.py rather than moving anywhere, because it coordinated
across roughly a dozen not-yet-extracted VaultManager methods and
splitting it out then would have meant threading that many hook
parameters through the single most safety-critical function in the app
for a mechanical file-organization win.

ADR-125 revisits that: `resolve_turn_context` is now decomposed into 8
small, independently-parametered `_resolve_*_case` methods (a separate,
prior change, not a file-organization move on its own), which removes the
parameter-threading risk this module's decision was originally about -
each case already takes only the few things it needs, not a dozen
dependencies threaded through one function. With that risk gone, the
whole cluster (the case methods, `_recall_hit`, `_recall_prep`,
`refresh_note_context`, `resolve_ritual_random_pull`, ...) moves to
`vault_turn_context.py` as a `TurnContextMixin` — a mixin, not free
functions, so `cls.read_note`/`cls.get_manifest`/etc. keep resolving
through `VaultManager`'s own MRO with no parameters threaded at all. This
module keeps the pieces that were always pure text processing with no
`cls` dependency, `describes_random_pull_ritual` included as of ADR-125 -
the anti-hallucination guarantee lives in how `resolve_turn_context` is
*used* (it only ever answers from a real retrieval, never a guess), not
in which file its orchestration code lives in.
"""

import re

from sympose.config import config_manager

# Lead-in phrases that precede the real subject of a conversational recall
# request. Longest-first so multi-word forms strip before their prefixes.
_RECALL_LEADINS: tuple[str, ...] = (
    "what have i written about",
    "what did i write about",
    "what did i say about",
    "what do i have on",
    "what do i have about",
    "what did i write",
    "what did i say",
    "do i have any notes about",
    "do i have any notes on",
    "do i have notes about",
    "do i have notes on",
    "do i have a note about",
    "do i have anything about",
    "do we have any notes about",
    "do we have notes on",
    "do we have anything about",
    "remind me about",
    "remind me of",
    "tell me about",
    "recall our",
    "recall my",
    "search for",
    "look for",
    "look up",
    "look at",
    "check for",
    "dig up",
    "dig out",
    "pull up",
    "pull out",
    "bring up",
    "show me",
    "find me",
    "get me",
    "how about",
    "what about",
    "anything about",
    "anything on",
    "my notes about",
    "my notes on",
    "notes about",
    "notes on",
    "note about",
    "note on",
    "my journal about",
    "journal entry about",
    "journal about",
    "journal on",
    "remind me",
    "recall",
    "remember when",
    "remember",
)
# Politeness / modal wrappers that sit in front of a recall lead-in
# ("can you pull up …", "please remind me …"). Stripped before the lead-in
# scan but — unlike a lead-in — not themselves treated as recall intent.
_RECALL_WRAPPERS: tuple[str, ...] = (
    "can you please",
    "could you please",
    "would you please",
    "can you kindly",
    "i want you to",
    "i'd like you to",
    "i would like you to",
    "i need you to",
    "can you",
    "could you",
    "would you",
    "will you",
    "can we",
    "could we",
    "can u",
    "cud u",
    "lets",
    "let's",
    "let us",
    "help me",
    "go ahead and",
    "please",
    "kindly",
    "pls",
    "plz",
)
# Tokens with no value as a substring search term; trimmed from both ends of
# an extracted subject.
_SUBJECT_STOPWORDS: frozenset = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "our",
        "your",
        "some",
        "any",
        "that",
        "this",
        "these",
        "up",
        "on",
        "in",
        "of",
        "for",
        "about",
        "regarding",
        "re",
        "from",
        "with",
        "please",
        "just",
        "also",
        "again",
        "vault",
        "obsidian",
        "note",
        "notes",
        "journal",
        "journals",
        "diary",
        "entry",
        "entries",
        "reflection",
        "reflections",
        "log",
        "logs",
        "did",
        "do",
        "i",
        "we",
        "you",
        "have",
        "had",
        "has",
        "write",
        "wrote",
        "written",
        "say",
        "said",
        "anything",
        "something",
        "stuff",
        "thing",
        "things",
        "and",
        "or",
        "me",
        "us",
        # sample / chrono filler — a "subject" made only of these is no subject
        "random",
        "randomly",
        "randam",
        "surprise",
        "whatever",
        "arbitrary",
        "daily",
        "recent",
        "latest",
        "old",
        "past",
        # stray retrieval verbs that can leak past the lead-in scan
        "grab",
        "get",
        "fetch",
        "pull",
        "bring",
        "show",
        "give",
        "pick",
        "choose",
    }
)


def _strip_leadin(q: str) -> tuple[str, bool]:
    """Strips politeness wrappers ('can you please …') and recall lead-ins
    ('pull up', 'tell me about', …) off the front of a clause, repeating
    until neither matches. Returns (remainder, had_leadin)."""
    had_leadin = False
    changed = True
    while changed:
        changed = False
        for phrase in _RECALL_WRAPPERS:
            if q.startswith(phrase + " "):
                q, changed = q[len(phrase) :].strip(), True
                break
        for phrase in _RECALL_LEADINS:
            if q.startswith(phrase + " "):
                q, changed, had_leadin = q[len(phrase) :].strip(), True, True
                break
    return q, had_leadin


def _trim_subject_clause(q: str) -> str:
    """Strips a trailing 'in my journal/vault/…' clause and everything past
    a conjunction, then trims stopwords from both ends of what remains."""
    m = re.search(
        r"\b(?:about|on|regarding|mentioning|discussing|concerning)\s+(.+)$", q
    )
    if m:
        q = m.group(1).strip()
    q = re.sub(
        r"\s+(?:in|from|within|inside)\s+(?:my|our|the\s+)?\s*"
        r"(?:journal|diary|vault|notes?|daily|entries|reflections?|logs?)\b.*$",
        "",
        q,
    ).strip()
    # A recall request rarely spans a conjunction ("… and see if my
    # memory's right"); keep only the head clause.
    q = re.split(r"\s+(?:and|but|so|then)\s+", q, maxsplit=1)[0].strip()
    toks = [t for t in re.split(r"\s+", q) if t]
    while toks and toks[0] in _SUBJECT_STOPWORDS:
        toks.pop(0)
    while toks and toks[-1] in _SUBJECT_STOPWORDS:
        toks.pop()
    return " ".join(toks).strip()


def _extract_subject_from_clause(q: str) -> tuple[str, bool]:
    """One clause's (subject, had_leadin) — lead-in/wrapper stripping, then
    subject trimming."""
    q, had_leadin = _strip_leadin(q)
    return _trim_subject_clause(q), had_leadin


def extract_recall_subject(message: str) -> tuple[str, bool]:
    """Best-effort extraction of the *subject* of a conversational recall
    request: 'pull up my notes on Rilke' -> 'rilke', 'what did I write about
    grief in my journal' -> 'grief'. Substring search needs a tight phrase;
    the whole lead-in-plus-subject string matches nothing. Returns
    (subject, had_leadin) — had_leadin is True when a recall phrasing
    ('tell me about', 'pull up', …) was consumed, which is itself a signal
    of vault intent even absent a trigger keyword."""
    raw = message.strip().strip("?.!").lower()
    raw = re.sub(
        r"^(?:hey|hi|hello|yo|good\s+\w+)[\s,]+(?:\w+[\s,]+)?", "", raw
    ).strip()
    # Possessive → bare stem so a substring search on "dylans" / "dylan's"
    # still matches the note that only ever spells it "Dylan".
    raw = re.sub(r"(\w)['’]s\b", r"\1", raw)

    # "i wish i could do that. can you pull up X" — process each sentence and
    # prefer the one that actually carries a recall lead-in.
    clauses = [c.strip() for c in re.split(r"[.?!]+\s+", raw) if c.strip()] or [raw]
    best = ("", False)
    for c in clauses:
        subj, lead = _extract_subject_from_clause(c)
        if lead and subj:
            return subj, True
        if subj and not best[0]:
            best = (subj, lead)
    return best


# The fixed set of keywords that flag a message as vault-related, regardless
# of caller (this module's own recall-intent check, and vault.py's separate
# directory-discovery trigger) — one canonical list instead of two
# independently hand-kept ones that had drifted out of agreement.
_BUILTIN_SEARCH_TRIGGERS: tuple[str, ...] = (
    "vault",
    "note",
    "notes",
    "folder",
    "journal",
    "backlink",
    "backlinks",
    "search",
    "find",
    "lookup",
    "look up",
    "recall",
    "remind me",
    "pull up",
    "what did i write",
    "what did i say",
    "do i have",
    "do we have",
)


def search_triggers() -> list[str]:
    """The full set of keywords that flag a message as a vault query: the
    fixed built-ins above, plus whatever `vault.search_triggers` adds on top.
    Additive, per that setting's own documented contract ("added to the
    built-ins") — a configured list augments this one, it doesn't replace
    it, so an explicit empty override (`[]`) is indistinguishable from no
    override and neither one can accidentally drop a built-in trigger."""
    extra = config_manager.get("vault.search_triggers") or []
    return [*_BUILTIN_SEARCH_TRIGGERS, *extra]


def has_recall_intent(message: str) -> bool:
    """True when the message is itself a fresh vault-recall request (a recall
    lead-in was consumed, or a configured search trigger appears). The engine
    uses this to decide *not* to reuse a previous turn's injected vault
    context when the current turn asked its own vault question and retrieval
    came back empty — answering a fresh 'pull up X' from a stale unrelated
    note is exactly the fabrication this guards against."""
    _, had_leadin = extract_recall_subject(message)
    if had_leadin:
        return True
    return any(k in message.lower() for k in search_triggers())


def describes_random_pull_ritual(fact: str) -> bool:
    """Generic detector for a persona-memory fact that itself describes a
    "pull a random note and discuss it" ritual, by whatever name the user
    gave it - not tied to any one wording or persona. Used to decide
    whether to honor such a fact for real (see
    VaultManager.resolve_ritual_random_pull) rather than let the model
    invent a plausible-sounding title."""
    low = (fact or "").lower()
    return "random" in low and any(
        w in low for w in ("note", "entry", "page", "pull", "pulled", "picked")
    )


def recall_candidates(subject: str, drop: str = "") -> list[str]:
    """Ordered search terms for a recall subject: the full phrase first, then
    its most-specific single tokens (longest, then earliest), then the
    de-pluralised stem of each so an apostrophe-less possessive ('dylans' ->
    'dylan') still matches. `drop` removes one token (e.g. the folder name)."""
    toks = {
        t
        for t in subject.split()
        if len(t) >= 3 and t not in _SUBJECT_STOPWORDS and t != drop
    }
    toks |= {t[:-1] for t in list(toks) if len(t) >= 5 and t.endswith("s")}
    ordered = [subject] + sorted(toks, key=lambda t: (-len(t), subject.find(t)))
    seen: set = set()
    out: list[str] = []
    for c in ordered:
        c = c.strip()
        if len(c) >= 3 and c not in seen:
            seen.add(c)
            out.append(c)
    return out
