"""The grounding retriever's index (docs/decisions/014): notes split into
passages, each with weighted term counts, plus how rare every term is across
notes. Plain data in, plain data out: it takes a list of note dicts (as
`vault_snapshot` produces them) and knows nothing about vaults, personas, or
sandboxing, so it can index any set of notes."""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sympose.vault_manifest_build import _stem, _tags_of

# Generic English filler, plus the product's own vocabulary: "note" and
# "vault" are in nearly every message to a notes assistant and say nothing
# about which note is meant.
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
    files""".split()
)

_WORD = re.compile(r"\w+")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_PASSAGE_CHARS = 400

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
    # Terms from the note's title, tags, or this passage's heading: a match on
    # one of these says the message is about this note, where a body-only
    # match on an ordinary word often does not.
    topical: frozenset[str]
    # Terms from the note's title alone (filename or `title:`), one set shared
    # by all of the note's passages. `tf` mixes them into every passage, so
    # this tells a message that is just a note's name from one that shares words
    # with the passage (docs/decisions/019).
    title_terms: frozenset[str]


@dataclass(frozen=True)
class Index:
    passages: list[Passage]
    note_df: dict[str, int]  # term -> number of notes containing it
    note_count: int
    avg_length: float


def _chunks(paragraph: str) -> list[str]:
    """One paragraph as pieces of at most `MAX_PASSAGE_CHARS`: cut at
    sentence ends where possible, at a word boundary where a single sentence
    is itself too long."""
    if len(paragraph) <= MAX_PASSAGE_CHARS:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > MAX_PASSAGE_CHARS:
            cut = sentence.rfind(" ", 0, MAX_PASSAGE_CHARS)
            if cut <= 0:  # no space to cut at (a long URL, say): hard cut
                cut = MAX_PASSAGE_CHARS
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        if current and len(current) + 1 + len(sentence) > MAX_PASSAGE_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def split_passages(body: str) -> list[tuple[str, str]]:
    """`(nearest_heading, text)` for each paragraph of `body`, where a
    paragraph is a run of lines between blank lines or headings. A fenced
    code block is one passage: a `# comment` inside it is code, not a
    heading, and the fence lines themselves are dropped."""
    heading = ""
    passages: list[tuple[str, str]] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        paragraph = " ".join(" ".join(buffer).split())
        buffer.clear()
        passages.extend((heading, piece) for piece in _chunks(paragraph) if piece)

    for line in body.splitlines():
        if line.strip().startswith(("```", "~~~")):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            if line.strip():
                buffer.append(line.strip())
            continue
        match = _HEADING.match(line)
        if match:
            flush()
            heading = match.group(1)
        elif not line.strip():
            flush()
        else:
            buffer.append(line.strip())
    flush()
    return passages


def build_index(notes: list[dict[str, Any]]) -> Index:
    """`notes`: dicts with `rel_path`, `file_name`, `meta`, `body`."""
    passages: list[Passage] = []
    note_df: Counter = Counter()
    note_count = 0
    for note in notes:
        meta = note.get("meta") or {}
        stem = _stem(note["file_name"])
        title = str(meta.get("title") or meta.get("name") or stem)
        tags = tuple(_tags_of(meta))
        header_terms = Counter()
        # A set: a title that equals the filename (the usual case) must not
        # count double.
        title_terms = frozenset(index_terms(f"{title} {stem}"))
        for term in title_terms:
            header_terms[term] += _TITLE_WEIGHT
        for term in index_terms(" ".join(tags)):
            header_terms[term] += _TAG_WEIGHT

        note_terms: set[str] = set()
        made_any = False
        for heading, text in split_passages(note.get("body") or ""):
            body_terms = index_terms(text)
            if not body_terms:
                # A rule ("---"), a stray marker, a passage of only filler
                # words: nothing to retrieve, and with a title boost and a
                # near-zero length it would otherwise outscore real text.
                continue
            tf = Counter(body_terms)
            heading_terms = index_terms(heading)
            for term in heading_terms:
                tf[term] += _HEADING_WEIGHT
            tf.update(header_terms)
            note_terms.update(tf)
            topical = frozenset(heading_terms) | frozenset(header_terms)
            passages.append(
                Passage(
                    note["rel_path"], title, heading, text, tags, tf, len(body_terms), topical, title_terms
                )
            )
            made_any = True
        if made_any:
            note_count += 1
            note_df.update(note_terms)
    avg = sum(p.length for p in passages) / len(passages) if passages else 0.0
    return Index(passages, dict(note_df), note_count, avg)
