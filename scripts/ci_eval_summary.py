"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: ci_eval_summary.py
@DateTime: 2026-05-20
@Docs: CI helper: summarize eval harness results for pipelines.
    CI 辅助：汇总 eval harness 结果供流水线使用。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render_markdown(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    failed = [item for item in data["results"] if not item["passed"]]
    lines = [
        "## Agent Eval",
        "",
        f"Result: **{data['passed']}/{data['total']} passed**",
        "",
    ]
    if failed:
        lines.append("Failed cases:")
        for item in failed:
            lines.append(f"- `{item['name']}`")
    else:
        lines.append("All eval cases passed.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    text = render_markdown(Path(args.json_path))
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
