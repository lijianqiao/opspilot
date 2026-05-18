"""Mock kubectl tools — reads from fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@register_tool
def kubectl_get(resource: str, namespace: str = "default") -> str:
    """查询 k8s 资源列表，类似 kubectl get。当前支持 pods。"""
    if resource == "pods":
        raw = json.loads(
            (_FIXTURES_DIR / "kubectl_pods.json").read_text(encoding="utf-8")
        )
        pods = [p for p in raw["pods"] if p["namespace"] == namespace]
        if not pods:
            return f"namespace {namespace} 下没有找到 pod。"
        lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
        lines += [
            f"{p['name']}\t{p['ready']}\t{p['status']}\t{p['restarts']}"
            for p in pods
        ]
        return "\n".join(lines)
    return f"暂不支持查询资源类型：{resource}"


@register_tool
def kubectl_describe(resource: str, name: str, namespace: str = "default") -> str:
    """查看 k8s 资源详情，类似 kubectl describe。返回 spec、status 和 events。"""
    raw = json.loads(
        (_FIXTURES_DIR / "kubectl_describe.json").read_text(encoding="utf-8")
    )
    for item in raw["resources"]:
        if (
            item["kind"] == resource
            and item["name"] == name
            and item["namespace"] == namespace
        ):
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
                    parts.append(
                        f"  {evt['type']} {evt['reason']}: {evt['message']} (x{evt['count']})"
                    )
            return "\n".join(parts)
    return f"没有找到 {resource}/{name} (namespace={namespace})。"
