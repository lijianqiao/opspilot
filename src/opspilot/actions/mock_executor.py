"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: mock_executor.py
@DateTime: 2026-05-20
@Docs: Mock ops backend executors used by generic service action tools.
    通用服务动作工具所使用的 mock 运维后端执行器。
"""

from __future__ import annotations


def restart_service_mock(service: str, env: str = "staging", strategy: str = "rolling") -> str:
    """Return a mock acknowledgement string for a service restart.
    返回服务重启的 mock 确认字符串。

    Args:
        service: Target service name.
            目标服务名称。
        env: Environment label (e.g. staging, prod).
            环境标签（如 staging、prod）。
        strategy: Restart strategy (default rolling).
            重启策略（默认 rolling）。

    Returns:
        Mock acknowledgement describing the submitted restart.
            描述已提交重启的 mock 确认信息。
    """
    return f"Mock {strategy} restart submitted for {env}/{service}."


def scale_service_mock(service: str, replicas: int, env: str = "staging") -> str:
    """Return a mock acknowledgement string for a scale operation.
    返回扩缩容操作的 mock 确认字符串。

    Args:
        service: Target service name.
            目标服务名称。
        replicas: Desired replica count.
            目标副本数。
        env: Environment label.
            环境标签。

    Returns:
        Mock acknowledgement describing the submitted scale request.
            描述已提交扩缩容请求的 mock 确认信息。
    """
    return f"Mock scale submitted for {env}/{service}: replicas -> {replicas}."


def remediation_mock(action: str, target: str, env: str = "staging") -> str:
    """Return a mock acknowledgement string for a named remediation action.
    返回具名补救动作的 mock 确认字符串。

    Args:
        action: Remediation action identifier (e.g. restart_db_pool).
            补救动作标识（如 restart_db_pool）。
        target: Target component or service name.
            目标组件或服务名称。
        env: Environment label.
            环境标签。

    Returns:
        Mock acknowledgement describing the submitted remediation.
            描述已提交补救动作的 mock 确认信息。
    """
    return f"Mock remediation submitted: action={action}, target={env}/{target}."
