"""The grounding retrieval eval as a test (docs/decisions/014): every case in
`grounding_cases.CASES` must pass against the real retriever on the synthetic
fixture vault. Deterministic, no model."""

import pytest
from grounding_cases import CASES, run_case, setup_env

from sympose.engine import grounding


def _param(case):
    marks = []
    if case.known_gap:
        # strict: if a case marked as a known gap starts passing (e.g. once
        # meaning-based matching exists), this fails so the marker gets
        # removed instead of silently hiding progress.
        marks.append(pytest.mark.xfail(reason=case.known_gap, strict=True))
    return pytest.param(case, id=case.id, marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_grounding_case(case, monkeypatch, tmp_path):
    setup_env(monkeypatch, str(tmp_path / "settings.json"))

    assert run_case(case, grounding.ground) is None
