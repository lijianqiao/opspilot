"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_runbook.py
@DateTime: 2026-05-20
@Docs: Tests retrieve_runbook keyword/RAG fallback paths.
    测试 retrieve_runbook 关键词/RAG 回退路径。
"""

from concurrent.futures import ThreadPoolExecutor

from opspilot.rag.retrieval import FALLBACK_RUNBOOK_TEXT
from opspilot.tools import runbook as runbook_mod
from opspilot.tools.runbook import _load_runbooks, retrieve_runbook


def test_retrieve_runbook_oom_match():
    """
    Verify retrieve runbook oom match.

    验证：retrieve runbook oom match。
    """
    result = retrieve_runbook("OOMKilled 内存溢出")
    assert "OOM" in result or "内存" in result


def test_retrieve_runbook_crashloop_match():
    """
    Verify retrieve runbook crashloop match.

    验证：retrieve runbook crashloop match。
    """
    result = retrieve_runbook("CrashLoopBackOff 反复重启")
    assert "CrashLoop" in result or "crash" in result.lower()


def test_retrieve_runbook_no_match_returns_generic():
    """
    Verify retrieve runbook no match returns generic.

    验证：retrieve runbook no match returns generic。
    """
    result = retrieve_runbook("unknown problem")
    assert result  # should return a generic runbook, not empty


def test_retrieve_runbook_exact_match():
    """
    Verify retrieve runbook exact match.

    验证：retrieve runbook exact match。
    """
    result = retrieve_runbook("CPU throttling 高负载")
    assert "CPU" in result


def test_keyword_fallback_uses_shared_constant() -> None:
    """
    Verify keyword fallback uses shared constant.

    验证：keyword fallback uses shared constant。
    """
    result = retrieve_runbook("unknown problem xyz")
    assert result == FALLBACK_RUNBOOK_TEXT


def test_load_runbooks_concurrent_is_idempotent() -> None:
    """
    Verify load runbooks concurrent is idempotent.

    验证：load runbooks concurrent is idempotent。
    """
    runbook_mod._RUNBOOKS = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _load_runbooks(), range(32)))
    assert all(r is results[0] for r in results)
    from opspilot.tools.fixtures_path import get_fixtures_dir

    fixture_count = len(list(get_fixtures_dir().glob("runbook_*.json")))
    assert len(results[0]) == fixture_count
    assert len(runbook_mod._RUNBOOKS) == fixture_count
