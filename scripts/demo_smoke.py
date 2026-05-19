from __future__ import annotations

import argparse
import json

import httpx


def build_demo_requests() -> list[dict[str, str]]:
    return [
        {"name": "pod-status", "question": "default 有哪些 pod 不正常"},
        {"name": "log-query", "question": "查一下 user-service 最近的错误日志"},
        {"name": "alert-triage", "question": "处理一个 CrashLoopBackOff 告警，给出根因和建议"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpsPilot demo smoke against agent-core HTTP API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{args.base_url}/healthz")
        health.raise_for_status()
        for item in build_demo_requests():
            resp = client.post(f"{args.base_url}/ask", json={"question": item["question"]})
            resp.raise_for_status()
            print(f"\n## {item['name']}\n")
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
