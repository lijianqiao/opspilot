import pytest

from opspilot.eval.cases import CASES
from opspilot.eval.harness import EvalResult, run_all


def test_there_are_fifteen_cases() -> None:
    assert len(CASES) == 15
    for c in CASES:
        assert c.question
        assert isinstance(c.scripted_replies, list) and c.scripted_replies


@pytest.mark.anyio
async def test_run_all_scores_three_metrics() -> None:
    results = await run_all()
    assert len(results) == 15
    for r in results:
        assert isinstance(r, EvalResult)
        assert r.tool_sequence_ok in (True, False)
        assert r.danger_blocked_ok in (True, False)
        assert r.answer_keywords_ok in (True, False)
    # the suite is designed so every case passes all 3 metrics
    assert all(r.passed for r in results), [r for r in results if not r.passed]
