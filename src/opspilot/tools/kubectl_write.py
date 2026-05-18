"""Mock kubectl WRITE tools — high risk, guarded by the guardrail layer."""

from __future__ import annotations

import json
from pathlib import Path

from opspilot.tools.registry import register_tool

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


def _load_deployments() -> list[dict[str, object]]:
    raw = json.loads((_FIXTURES_DIR / "kubectl_write.json").read_text(encoding="utf-8"))
    return raw["deployments"]


@register_tool(risk="high")
def kubectl_scale(deployment: str, replicas: int, namespace: str = "default") -> str:
    """伸缩 deployment 副本数（写操作，高危）。"""
    for d in _load_deployments():
        if d["name"] == deployment and d["namespace"] == namespace:
            return f"deployment.apps/{deployment} scaled: {d['replicas']} -> {replicas} (namespace={namespace})"
    return f"没有找到 deployment {deployment} (namespace={namespace})。"


@register_tool(risk="high")
def kubectl_rollout_restart(deployment: str, namespace: str = "default") -> str:
    """滚动重启 deployment（写操作，高危）。"""
    for d in _load_deployments():
        if d["name"] == deployment and d["namespace"] == namespace:
            return f"deployment.apps/{deployment} 已触发滚动重启 (namespace={namespace})"
    return f"没有找到 deployment {deployment} (namespace={namespace})。"
