"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_kubectl_policy.py
@DateTime: 2026-05-20
@Docs: Tests kubectl read policy and real-mode subprocess guards.
    测试 kubectl 只读策略与真实模式下的 subprocess 防护。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear Settings LRU cache before and after each test.

    每个测试前后清空 Settings 的 LRU 缓存。
    """
    from opspilot.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_kubectl_get_rejects_sensitive_resource_before_real_subprocess(monkeypatch) -> None:
    """
    Verify kubectl get rejects sensitive resource before real subprocess.

    验证：kubectl get rejects sensitive resource before real subprocess。
    """
    from opspilot.config import get_settings
    from opspilot.tools import fixtures_path
    from opspilot.tools.kubectl_ops import kubectl_get

    get_settings.cache_clear()
    monkeypatch.setenv("OPSPILOT_USE_MOCK_TOOLS", "false")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(fixtures_path.subprocess, "run", fail_run)

    result = kubectl_get("secrets")

    assert "敏感" in result


def test_kubectl_describe_rejects_unsupported_resource_before_real_subprocess(monkeypatch) -> None:
    """
    Verify kubectl describe rejects unsupported resource before real subprocess.

    验证：kubectl describe rejects unsupported resource before real subprocess。
    """
    from opspilot.config import get_settings
    from opspilot.tools import fixtures_path
    from opspilot.tools.kubectl_ops import kubectl_describe

    get_settings.cache_clear()
    monkeypatch.setenv("OPSPILOT_USE_MOCK_TOOLS", "false")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(fixtures_path.subprocess, "run", fail_run)

    result = kubectl_describe("deployment", "web")

    assert "暂不支持" in result


def test_kubectl_describe_real_rejects_sensitive_resource_before_subprocess(monkeypatch) -> None:
    """
    Verify kubectl describe real rejects sensitive resource before subprocess.

    验证：kubectl describe real rejects sensitive resource before subprocess。
    """
    from opspilot.tools import fixtures_path

    def fail_run(*_args, **_kwargs):
        raise AssertionError("subprocess should not be called")

    monkeypatch.setattr(fixtures_path.subprocess, "run", fail_run)

    result = fixtures_path.kubectl_describe_real("configmap", "app-config", "default")

    assert "敏感" in result


def test_kubectl_get_pods_still_calls_real_subprocess(monkeypatch) -> None:
    """
    Verify kubectl get pods still calls real subprocess.

    验证：kubectl get pods still calls real subprocess。
    """
    from opspilot.config import get_settings
    from opspilot.tools import fixtures_path
    from opspilot.tools.kubectl_ops import kubectl_get

    get_settings.cache_clear()
    monkeypatch.setenv("OPSPILOT_USE_MOCK_TOOLS", "false")
    calls = []

    class Proc:
        returncode = 0
        stdout = "NAME READY STATUS RESTARTS\npod-a 1/1 Running 0\n"
        stderr = ""

    def fake_run(args, **_kwargs):
        calls.append(args)
        return Proc()

    monkeypatch.setattr(fixtures_path.subprocess, "run", fake_run)

    result = kubectl_get("pods")

    assert "pod-a" in result
    assert calls == [["kubectl", "get", "pods", "-n", "default"]]
