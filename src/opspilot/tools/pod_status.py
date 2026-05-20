"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: pod_status.py
@DateTime: 2026-05-20
@Docs: Mock pod status tool reading kubectl-style fixtures.
    模拟 Pod 状态查询工具，从 fixture 读取数据。
"""

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@register_tool
def get_pod_status(namespace: str = "default") -> str:
    """Query pod status in a namespace (kubectl get pods style table).
    查询指定 namespace 下的 pod 状态，返回类似 kubectl get pods 的文本表。

    Args:
        namespace: Kubernetes namespace to list pods in.
            要列出 Pod 的 Kubernetes 命名空间。

    Returns:
        Tabular pod listing or message when none found.
            Pod 列表表格文本，无 Pod 时返回提示信息。
    """
    raw = (FIXTURES_DIR / "kubectl_pods.json").read_text(encoding="utf-8")
    pods = [p for p in json.loads(raw)["pods"] if p["namespace"] == namespace]
    if not pods:
        return f"namespace {namespace} 下没有找到 pod。"
    lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
    lines += [f"{p['name']}\t{p['ready']}\t{p['status']}\t{p['restarts']}" for p in pods]
    return "\n".join(lines)
