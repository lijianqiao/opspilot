import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


def get_pod_status(namespace: str = "default") -> str:
    """查询指定 namespace 下的 pod 状态，返回类似 kubectl get pods 的文本表。"""
    raw = (FIXTURES_DIR / "kubectl_pods.json").read_text(encoding="utf-8")
    pods = [p for p in json.loads(raw)["pods"] if p["namespace"] == namespace]
    if not pods:
        return f"namespace {namespace} 下没有找到 pod。"
    lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
    lines += [f"{p['name']}\t{p['ready']}\t{p['status']}\t{p['restarts']}" for p in pods]
    return "\n".join(lines)
