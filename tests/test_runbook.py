from opspilot.tools.runbook import retrieve_runbook


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
