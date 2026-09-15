"""
Conversational-recall subject extraction: turning a natural request like
"pull up my notes on grief" or "what did I write about Rilke" into a clean
search term, and detecting whether a message is itself a fresh recall
request at all.

`resolve_turn_context` — the orchestrator that ties this together with
nearly every other vault capability (search, backlinks, folder discovery,
the manifest digest, chronological sampling) to answer a turn from real
vault content, or not at all — deliberately stays a VaultManager method in
vault.py rather than moving here. It coordinates across roughly a dozen
not-yet-extracted VaultManager methods (read_note, get_manifest,
find_chronological_notes, get_discovered_folders, get_random_sample_notes,
get_folder_digest, has_vault_skill, ...); splitting it out would mean
threading that many hook parameters through the single most
safety-critical function in the app for a mechanical file-organization
win. The actual anti-hallucination guarantee lives in how this function is
*used* — it only ever answers from a real retrieval, never a guess — not
in which file its orchestration code lives in, so this was judged not
worth the added risk. What moved here is everything self-contained: pure
text processing, no I/O, no cross-cluster dependency.
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
        # "let's play our favorite game" names an established ritual (Sympose's
        # own "Vault/Note Roulette" - a random-note pull), not a vault topic;
        # these describe the activity itself, never something worth searching
        # note bodies for.
        "game",
        "play",
        "favorite",
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

    def _from_clause(q: str) -> tuple[str, bool]:
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
        return " ".join(toks).strip(), had_leadin

    # "i wish i could do that. can you pull up X" — process each sentence and
    # prefer the one that actually carries a recall lead-in.
    clauses = [c.strip() for c in re.split(r"[.?!]+\s+", raw) if c.strip()] or [raw]
    best = ("", False)
    for c in clauses:
        subj, lead = _from_clause(c)
        if lead and subj:
            return subj, True
        if subj and not best[0]:
            best = (subj, lead)
    return best


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
    triggers = config_manager.get("vault.search_triggers") or [
        "vault",
        "note",
        "notes",
        "journal",
        "recall",
    ]
    return any(k in message.lower() for k in triggers)


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
