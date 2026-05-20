from concurrent.futures import ThreadPoolExecutor

from opspilot.rag.retrieval import FALLBACK_RUNBOOK_TEXT
from opspilot.tools import runbook as runbook_mod
from opspilot.tools.runbook import _load_runbooks, retrieve_runbook


def test_retrieve_runbook_oom_match():
    result = retrieve_runbook("OOMKilled 内存溢出")
    assert "OOM" in result or "内存" in result


def test_retrieve_runbook_crashloop_match():
    result = retrieve_runbook("CrashLoopBackOff 反复重启")
    assert "CrashLoop" in result or "crash" in result.lower()


def test_retrieve_runbook_no_match_returns_generic():
    result = retrieve_runbook("unknown problem")
    assert result  # should return a generic runbook, not empty


def test_retrieve_runbook_exact_match():
    result = retrieve_runbook("CPU throttling 高负载")
    assert "CPU" in result


def test_keyword_fallback_uses_shared_constant() -> None:
    result = retrieve_runbook("unknown problem xyz")
    assert result == FALLBACK_RUNBOOK_TEXT


def test_load_runbooks_concurrent_is_idempotent() -> None:
    runbook_mod._RUNBOOKS = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _load_runbooks(), range(32)))
    assert all(r is results[0] for r in results)
    fixture_count = len(list(runbook_mod._FIXTURES_DIR.glob("runbook_*.json")))
    assert len(results[0]) == fixture_count
    assert len(runbook_mod._RUNBOOKS) == fixture_count
