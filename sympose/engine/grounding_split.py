"""Cutting a note's body into passages (docs/decisions/014): paragraphs between blank lines and headings, a
fenced code block as one passage, long paragraphs cut at sentence ends. Plain text in, plain text out; it knows
nothing about terms, weights or vaults (`grounding_index` does)."""

import re

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\w")
MAX_PASSAGE_CHARS = 400


def has_words(text: str) -> bool:
    """Whether `text` has a letter or a digit: a rule (`---`) or a stray marker does not."""
    return bool(_WORD.search(text))


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


def _is_fence(line: str) -> bool:
    """A fence marker: three or more tildes, or backticks with none after them on the line (a line
    such as ```py x``` opens and closes on itself, so it is inline code, not a fence)."""
    stripped = line.strip()
    if stripped.startswith("~~~"):
        return True
    return stripped.startswith("```") and "`" not in stripped.lstrip("`")


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
        if _is_fence(line):
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


def headings_of(body: str) -> list[str]:
    """The headings of a note that has no text under them, as many as fit in one passage: only those with
    words in them (so a `# ---` line of a code block is not one; a block with words in it is text, and this is
    not asked)."""
    kept: list[str] = []
    size = 0
    for line in body.splitlines():
        match = _HEADING.match(line)
        if match and has_words(match.group(1)):
            size += len(match.group(1)) + 2
            if size > MAX_PASSAGE_CHARS:
                break
            kept.append(match.group(1))
    return kept
