"""The grounding retriever's index (docs/decisions/014): notes split into
passages, each with weighted term counts, plus how rare every term is across
notes. Plain data in, plain data out: it takes a list of note dicts (as
`vault_snapshot` produces them) and knows nothing about vaults, personas, or
sandboxing, so it can index any set of notes."""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sympose.engine.grounding_split import MAX_PASSAGE_CHARS, has_words, headings_of, split_passages  # noqa: F401
from sympose.vault_manifest_build import _stem, _tags_of

# Generic English filler, plus the product's own vocabulary: "note" and
# "vault" are in nearly every message to a notes assistant and say nothing
# about which note is meant. Contractions typed without their apostrophe
# ("whats", "arent") are the same filler: with the apostrophe the tokenizer
# already splits them into filler (docs/decisions/021). Only those that are
# nothing else: "id", "ill", "cant" and "wont" are words in their own right.
STOPWORDS = frozenset(
    """a about above after again all also am an and any are as at be because
    been before being below between both but by can could did do does doing
    down during each few for from further had has have having he her here
    hers him his how i if in into is it its just me more most my no nor not
    now of off on once only or other our ours out over own same she should so
    some such than that the their theirs them then there these they this
    those through to too under until up very was we were what when where
    which while who whom why will with would you your yours hey hi hello yes
    ok okay please thanks thank tell say said give get got let lets like want
    need know think thing things one ones really much many something anything
    everything maybe still ever going go make made note notes vault file
    files
    whats thats hows wheres theres heres whos im ive youre youve youll youd hes
    shes isnt arent wasnt werent dont doesnt didnt couldnt wouldnt shouldnt
    havent hasnt hadnt""".split()
)

_WORD = re.compile(r"\w+")
PASSAGES_PER_NOTE = 2  # at most this many passages of one note are attached (by keyword or by meaning)

# How much a term's appearance counts by where it appears: a note's title or
# tag says far more about what it is than one word of its body does.
_TITLE_WEIGHT, _TAG_WEIGHT, _HEADING_WEIGHT = 3, 3, 2


def fold(word: str) -> str:
    """Plural-'s' folding so "flights" matches "flight". Applied to both the
    index and the query, so the folded form never needs to be a real word."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def index_terms(text: str) -> list[str]:
    return [fold(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 1]


@dataclass(frozen=True)
class Passage:
    rel_path: str
    title: str
    heading: str
    text: str
    tags: tuple[str, ...]
    tf: Counter  # weighted term counts (body + title/tag/heading, boosted)
    length: int  # body terms, for length normalization
    # The term sets of the passage's own labels: its note's title, the filename when it
    # differs, each tag, and this passage's heading. A message that names half of one of
    # them is about this note, where an ordinary word of a longer label, or of the body,
    # often is not (docs/decisions/024).
    labels: tuple[frozenset[str], ...]
    # Terms from the note's title alone (filename or `title:`), one set shared
    # by all of the note's passages. `tf` mixes them into every passage, so
    # this tells a message that is just a note's name from one that shares words
    # with the passage (docs/decisions/019).
    title_terms: frozenset[str]
    # "text": a paragraph of the body. "title": the note has no body text, so the title (and its
    # aliases, as the text) stands for it; the prompt says so (docs/decisions/030).
    kind: str = "text"


@dataclass(frozen=True)
class Index:
    passages: list[Passage]
    note_df: dict[str, int]  # term -> number of notes containing it
    note_count: int
    avg_length: float


def _aliases_of(meta: dict[str, Any]) -> list[str]:
    """The other names of a note (`aliases:`, and the older `alias:`): a list of names, or one string that
    may hold several separated by commas; each name once; anything that is not text is ignored."""
    names: list[str] = []
    for key in ("aliases", "alias"):
        value = meta.get(key)
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            names += [name.strip() for name in value if isinstance(name, str) and name.strip()]
    seen: set[str] = set()
    return [name for name in names if not (name.lower() in seen or seen.add(name.lower()))]


def _note_passages(note: dict[str, Any]) -> list[Passage]:
    """The passages of one note: its body paragraphs; else, when everything in it is filler words, those
    (findable by the title, shown as the text they are); else, when it has no text, its title, aliases and
    headings as one passage that says so (docs/decisions/030)."""
    meta = note.get("meta") or {}
    stem = _stem(note["file_name"])
    title = str(meta.get("title") or meta.get("name") or stem)
    tags = tuple(_tags_of(meta))
    aliases = _aliases_of(meta)
    # A set: a title that equals the filename (the usual case) must not count double. The aliases are
    # other names for the same title.
    title_terms = frozenset(index_terms(f"{title} {stem} {' '.join(aliases)}"))
    header = Counter({term: _TITLE_WEIGHT for term in title_terms})
    for term in index_terms(" ".join(tags)):
        header[term] += _TAG_WEIGHT

    def passage(heading: str, text: str, body_terms: list[str], length: int, labelled: tuple[str, ...], kind: str = "text"):
        tf = Counter(body_terms)
        for term in index_terms(heading):
            tf[term] += _HEADING_WEIGHT
        tf.update(header)
        labels = tuple(dict.fromkeys(frozenset(index_terms(label)) for label in (title, stem, *aliases, *tags, *labelled)))
        return Passage(note["rel_path"], title, heading, text, tags, tf, length, labels, title_terms, kind)

    body = note.get("body") or ""
    found: list[Passage] = []
    filler: list[tuple[str, str]] = []
    for heading, text in split_passages(body):
        body_terms = index_terms(text)
        if body_terms:
            found.append(passage(heading, text, body_terms, len(body_terms), (heading,)))
        elif has_words(text):
            filler.append((heading, text))
        # else a rule or a stray marker: nothing to retrieve, and with a title boost and a near-zero
        # length it would otherwise outscore real text.
    if found:
        return found  # (a filler-only paragraph beside real text is dropped for the same reason)
    if filler:
        return [passage(h, t, [], max(1, len(title_terms)), (h,)) for h, t in filler] if header else []
    headings = headings_of(body)
    if not header and not index_terms(" ".join(headings)):
        return []
    return [passage(", ".join(headings), ", ".join(aliases), [], len(title_terms) + len(index_terms(" ".join(headings))), tuple(headings), "title")]


def build_index(notes: list[dict[str, Any]]) -> Index:
    """`notes`: dicts with `rel_path`, `file_name`, `meta`, `body`."""
    passages: list[Passage] = []
    note_df: Counter = Counter()
    note_count = 0
    for note in notes:
        made = _note_passages(note)
        if made:
            note_count += 1
            note_df.update(set().union(*(p.tf.keys() for p in made)))
            passages += made
    avg = sum(p.length for p in passages) / len(passages) if passages else 0.0
    return Index(passages, dict(note_df), note_count, avg)
