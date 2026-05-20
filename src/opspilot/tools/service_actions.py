"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: service_actions.py
@DateTime: 2026-05-20
@Docs: Generic high-risk service action tools (restart/scale/remediation).
    通用高危服务动作工具（重启/扩缩容/补救动作）。
"""

from __future__ import annotations

from opspilot.actions.mock_executor import remediation_mock, restart_service_mock, scale_service_mock
from opspilot.tools.registry import register_tool


@register_tool(risk="high", reversible=False)
def restart_service(service: str, env: str = "staging", strategy: str = "rolling") -> str:
    """Restart a service through the configured operations backend.
    通过当前配置的运维后端重启服务。

    Args:
        service: Target service name.
            目标服务名称。
        env: Environment label (e.g. staging, prod).
            环境标签（如 staging、prod）。
        strategy: Restart strategy (default rolling).
            重启策略（默认 rolling）。

    Returns:
        Backend acknowledgement string (mock by default).
            后端确认字符串（默认 mock）。
    """
    return restart_service_mock(service=service, env=env, strategy=strategy)


@register_tool(risk="high", reversible=False)
def scale_service(service: str, replicas: int, env: str = "staging") -> str:
    """Scale a service through the configured operations backend.
    通过当前配置的运维后端伸缩服务副本数。

    Args:
        service: Target service name.
            目标服务名称。
        replicas: Desired replica count.
            目标副本数。
        env: Environment label.
            环境标签。

    Returns:
        Backend acknowledgement string (mock by default).
            后端确认字符串（默认 mock）。
    """
    return scale_service_mock(service=service, replicas=replicas, env=env)


@register_tool(risk="high", reversible=False)
def run_remediation(action: str, target: str, env: str = "staging") -> str:
    """Run a named remediation action through the configured operations backend.
    通过当前配置的运维后端执行具名补救动作。

    Args:
        action: Remediation action identifier.
            补救动作标识。
        target: Target component or service name.
            目标组件或服务名称。
        env: Environment label.
            环境标签。

    Returns:
        Backend acknowledgement string (mock by default).
            后端确认字符串（默认 mock）。
    """
    return remediation_mock(action=action, target=target, env=env)
