"""Tests for sympose.engine.reply_text (docs/decisions/007, update): the whitespace habits of a
small model are removed from a reply, and code is left alone."""

import pytest

from sympose.engine import reply_text

tidy = reply_text.tidy


@pytest.mark.parametrize(
    "raw, clean",
    [
        ("Hello there!  \n\n\n", "Hello there!"),
        ("\n\n  Hello", "Hello"),
        ("Hey! \n", "Hey!"),
        ("One.  Two!  Three?  Four\u2026  Five", "One. Two! Three? Four\u2026 Five"),
        ("First.\n\n\n\nSecond.", "First.\n\nSecond."),
        ("First.\n\nSecond.", "First.\n\nSecond."),
        ("a, b  c", "a, b  c"),  # only after a sentence: two spaces mid-sentence are not touched
        ("Done.\n  next line", "Done.\n  next line"),  # an indented line is not "after a sentence"
    ],
)
def test_the_habits_are_removed(raw, clean):
    assert tidy(raw) == clean


def test_code_is_left_exactly_as_written():
    raw = "Try this:  \n```python\nx = 1.  y\n\n\n\nz\n```\nDone.  Really.  \n\n"
    assert tidy(raw) == "Try this:  \n```python\nx = 1.  y\n\n\n\nz\n```\nDone. Really."


def test_an_unclosed_fence_keeps_everything_after_it():
    assert tidy("Look.  \n```\na.  b\n\n\n\nc") == "Look.  \n```\na.  b\n\n\n\nc"


def test_a_first_line_indented_as_code_keeps_its_indent():
    assert tidy("\n    indented()\nrest") == "    indented()\nrest"


def test_a_reply_of_only_whitespace_is_empty():
    assert tidy(" \n\n \t\n") == ""
    assert tidy("") == ""
