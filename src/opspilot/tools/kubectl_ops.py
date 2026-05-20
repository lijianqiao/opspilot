"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: kubectl_ops.py
@DateTime: 2026-05-20
@Docs: Mock read-only kubectl tools (get, describe) from fixtures.
    模拟只读 kubectl 工具（get、describe），数据来自 fixture。
"""

from __future__ import annotations

import json

from opspilot.tools.fixtures_path import (
    kubectl_describe_real,
    kubectl_get_pods_real,
    read_fixture_json,
    use_mock_tools,
)
from opspilot.tools.registry import register_tool


@register_tool
def kubectl_get(resource: str, namespace: str = "default") -> str:
    """List Kubernetes resources (kubectl get style); pods supported.
    查询 k8s 资源列表，类似 kubectl get。当前支持 pods。

    Args:
        resource: Resource type (e.g. pods).
            资源类型（如 pods）。
        namespace: Namespace to query.
            要查询的命名空间。

    Returns:
        Tabular listing or unsupported-resource message.
            表格化列表或不支持资源类型的提示。
    """
    if resource == "pods":
        if not use_mock_tools():
            return kubectl_get_pods_real(namespace)
        raw = read_fixture_json("kubectl_pods.json")
        assert isinstance(raw, dict)
        pods = [p for p in raw["pods"] if p["namespace"] == namespace]
        if not pods:
            return f"namespace {namespace} 下没有找到 pod。"
        lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
        lines += [f"{p['name']}\t{p['ready']}\t{p['status']}\t{p['restarts']}" for p in pods]
        return "\n".join(lines)
    return f"暂不支持查询资源类型：{resource}"


@register_tool
def kubectl_describe(resource: str, name: str, namespace: str = "default") -> str:
    """Describe a Kubernetes resource (spec, status, events).
    查看 k8s 资源详情，类似 kubectl describe。返回 spec、status 和 events。

    Args:
        resource: Resource kind (e.g. pod).
            资源种类（如 pod）。
        name: Resource name.
            资源名称。
        namespace: Resource namespace.
            资源命名空间。

    Returns:
        Formatted describe output or not-found message.
            格式化的 describe 输出或未找到提示。
    """
    if not use_mock_tools():
        return kubectl_describe_real(resource, name, namespace)
    raw = read_fixture_json("kubectl_describe.json")
    assert isinstance(raw, dict)
    for item in raw["resources"]:
        if item["kind"] == resource and item["name"] == name and item["namespace"] == namespace:
            parts = [
                f"Name: {item['name']}",
                f"Namespace: {item['namespace']}",
                f"Kind: {item['kind']}",
                "",
                "Spec:",
                json.dumps(item["spec"], indent=2, ensure_ascii=False),
                "",
                "Status:",
                json.dumps(item["status"], indent=2, ensure_ascii=False),
            ]
            if item.get("events"):
                parts.append("\nEvents:")
                for evt in item["events"]:
                    parts.append(f"  {evt['type']} {evt['reason']}: {evt['message']} (x{evt['count']})")
            return "\n".join(parts)
    return f"没有找到 {resource}/{name} (namespace={namespace})。"
