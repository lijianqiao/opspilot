"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_eval_harness.py
@DateTime: 2026-05-20
@Docs: Tests offline eval harness three-metric scoring.
    测试离线 eval 三指标评分 harness。
"""

import pytest

from opspilot.eval.cases import CASES
from opspilot.eval.harness import EvalResult, run_all


def test_there_are_fifteen_cases() -> None:
    """
    Verify there are fifteen cases.

    验证：there are fifteen cases。
    """
    assert len(CASES) == 18
    for c in CASES:
        assert c.question
        assert isinstance(c.scripted_replies, list) and c.scripted_replies


@pytest.mark.anyio
async def test_run_all_scores_three_metrics() -> None:
    """
    Verify run all scores three metrics.

    验证：run all scores three metrics。
    """
    results = await run_all()
    assert len(results) == 18
    for r in results:
        assert isinstance(r, EvalResult)
        assert r.tool_sequence_ok in (True, False)
        assert r.danger_blocked_ok in (True, False)
        assert r.answer_keywords_ok in (True, False)
    # the suite is designed so every case passes all 3 metrics
    assert all(r.passed for r in results), [r for r in results if not r.passed]
