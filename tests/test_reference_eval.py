"""The reference-library eval as a test: every case in
`reference_cases` must pass against the real retriever on the shipped notes in
sympose/reference/. Deterministic, no model."""

import os
import re
import tomllib

import pytest
from reference_cases import REF_CASES, REFERENCE_DIR, VAULT_QUESTIONS_MUST_NOT_ATTACH, run_ref_case

from sympose.engine.grounding_index import MAX_PASSAGE_CHARS


def _param(case):
    marks = []
    if case.known_gap:
        marks.append(pytest.mark.xfail(reason=case.known_gap, strict=True))
    return pytest.param(case, id=case.id, marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in REF_CASES + VAULT_QUESTIONS_MUST_NOT_ATTACH])
def test_reference_case(case):
    assert run_ref_case(case) is None


def _notes() -> list[tuple[str, str]]:
    """`(file name, text)` for every note: only markdown, as the retriever reads."""
    names = sorted(n for n in os.listdir(REFERENCE_DIR) if n.endswith(".md"))
    return [(n, open(os.path.join(REFERENCE_DIR, n), encoding="utf-8").read()) for n in names]


def test_the_library_is_not_empty():
    assert len(_notes()) >= 10


def test_every_reference_answer_fits_one_passage():
    # The retriever hands the model at most two passages of this size per
    # note, so an answer that is cut in two can lose its second half. A
    # heading on the line just above its answer is not part of the answer.
    too_long = []
    for name, text in _notes():
        for block in text.split("\n\n"):
            if block.startswith("```"):
                continue
            answer = " ".join(" ".join(line for line in block.splitlines() if not line.startswith("#")).split())
            if len(answer) > MAX_PASSAGE_CHARS:
                too_long.append(f"{name}: {answer[:40]!r}")
    assert too_long == []


def test_every_reference_note_starts_with_its_own_title():
    for name, text in _notes():
        assert text.splitlines()[0] == f"# {name.removesuffix('.md')}", name


def test_a_version_named_in_the_library_is_the_packages_version():
    # The one fact in the notes that changes on every release; the rest of
    # keeping the notes true is not automated yet (docs/decisions/019).
    with open(os.path.join(REFERENCE_DIR, "..", "..", "pyproject.toml"), "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    named = {m for _, text in _notes() for m in re.findall(r"version (\d+\.\d+\.\d+)", text)}
    assert named == {version}
