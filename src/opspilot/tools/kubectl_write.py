"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: kubectl_write.py
@DateTime: 2026-05-20
@Docs: Mock high-risk kubectl write tools and rollback metadata helper.
    模拟高风险 kubectl 写操作工具及回滚元数据辅助函数。
"""

from __future__ import annotations

import json

from opspilot.tools.fixtures_path import read_fixture_json, use_mock_tools
from opspilot.tools.registry import register_tool


def _load_deployments() -> list[dict[str, object]]:
    if not use_mock_tools():
        return []
    raw = read_fixture_json("kubectl_write.json")
    assert isinstance(raw, dict)
    return raw["deployments"]


@register_tool(risk="high")
def kubectl_scale(deployment: str, replicas: int, namespace: str = "default") -> str:
    """Scale a deployment replica count (high-risk write).
    伸缩 deployment 副本数（写操作，高危）。

    Args:
        deployment: Deployment name.
            Deployment 名称。
        replicas: Target replica count.
            目标副本数。
        namespace: Deployment namespace.
            Deployment 命名空间。

    Returns:
        Mock scale result or not-found message.
            模拟扩缩容结果或未找到提示。
    """
    if not use_mock_tools():
        return "真实集群模式下 kubectl_scale 尚未实现，请使用 mock 联调或自行扩展。"
    for d in _load_deployments():
        if d["name"] == deployment and d["namespace"] == namespace:
            return f"deployment.apps/{deployment} scaled: {d['replicas']} -> {replicas} (namespace={namespace})"
    return f"没有找到 deployment {deployment} (namespace={namespace})。"


@register_tool(risk="high")
def kubectl_rollout_restart(deployment: str, namespace: str = "default") -> str:
    """Rolling restart a deployment (high-risk write).
    滚动重启 deployment（写操作，高危）。

    Args:
        deployment: Deployment name.
            Deployment 名称。
        namespace: Deployment namespace.
            Deployment 命名空间。

    Returns:
        Mock restart acknowledgment or not-found message.
            模拟重启确认或未找到提示。
    """
    if not use_mock_tools():
        return "真实集群模式下 kubectl_rollout_restart 尚未实现，请使用 mock 联调或自行扩展。"
    for d in _load_deployments():
        if d["name"] == deployment and d["namespace"] == namespace:
            return f"deployment.apps/{deployment} 已触发滚动重启 (namespace={namespace})"
    return f"没有找到 deployment {deployment} (namespace={namespace})。"


def rollback_info_for(tool_name: str, raw_input: str) -> dict[str, object] | None:
    """Return pre-state snapshot for rollback without side effects.
    给定将要执行的写操作，返回回滚所需的前置状态（不产生副作用）。

    Args:
        tool_name: kubectl_scale or kubectl_rollout_restart.
            工具名：kubectl_scale 或 kubectl_rollout_restart。
        raw_input: JSON Action Input with deployment/namespace fields.
            含 deployment/namespace 等字段的 JSON Action Input。

    Returns:
        Rollback dict (replicas or revision) or None if parse/lookup fails.
            回滚字典（副本数或 revision），解析或查找失败时为 None。
    """
    try:
        args = json.loads(raw_input)
        if not isinstance(args, dict):
            return None
    except (json.JSONDecodeError, TypeError):
        return None

    deployment = args.get("deployment")
    namespace = args.get("namespace", "default")
    if tool_name == "kubectl_scale" and deployment:
        for d in _load_deployments():
            if d["name"] == deployment and d["namespace"] == namespace:
                return {"deployment": deployment, "replicas": d["replicas"], "namespace": namespace}
    if tool_name == "kubectl_rollout_restart" and deployment:
        for d in _load_deployments():
            if d["name"] == deployment and d["namespace"] == namespace:
                return {"deployment": deployment, "revision": d.get("revision", "unknown"), "namespace": namespace}
    return None
