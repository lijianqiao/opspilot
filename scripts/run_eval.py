"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: run_eval.py
@DateTime: 2026-05-20
@Docs: CLI: run offline eval harness and print score table.
    CLI：运行离线 eval 并打印评分表。

Usage:
    uv run python scripts/run_eval.py
"""

import argparse
import json

import anyio

from opspilot.eval.harness import format_table, run_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", default="")
    args = parser.parse_args()

    results = anyio.run(run_all)
    print(format_table(results))

    if args.json_output:
        payload = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "results": [
                {
                    "name": r.name,
                    "tool_sequence_ok": r.tool_sequence_ok,
                    "danger_blocked_ok": r.danger_blocked_ok,
                    "answer_keywords_ok": r.answer_keywords_ok,
                    "passed": r.passed,
                }
                for r in results
            ],
        }
        with open(args.json_output, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if not all(r.passed for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
