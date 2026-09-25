"""Tidying a model's reply (docs/decisions/007): the whitespace habits a small model has,
removed once at the source so they are not shown, saved, or sent back as history."""

import re

_AFTER_SENTENCE = re.compile(r"(?<=[.!?\u2026]) {2,}(?=\S)")
_BLANK_RUN = re.compile(r"\n{3,}")
_LEADING_BLANK_LINES = re.compile(r"\A(?:[ \t]*\n)+")
_LEADING_SPACES = re.compile(r"\A {1,3}(?=\S)")  # four or more is an indented code block


def tidy(text: str) -> str:
    """No blank lines or stray spaces at either end, one blank line at most between paragraphs, one space
    after a sentence. Text between triple backticks is code and stays as written."""
    parts = text.split("```")
    for i in range(0, len(parts), 2):  # even parts are outside the code fences
        parts[i] = _BLANK_RUN.sub("\n\n", _AFTER_SENTENCE.sub(" ", parts[i]))
    text = "```".join(parts).rstrip()
    return _LEADING_SPACES.sub("", _LEADING_BLANK_LINES.sub("", text))
