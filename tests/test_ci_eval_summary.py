"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_ci_eval_summary.py
@DateTime: 2026-05-20
@Docs: Tests CI eval summary script output contract.
    测试 CI 评估汇总脚本输出约定。
"""

import json
from pathlib import Path

from scripts.ci_eval_summary import render_markdown


def test_render_markdown_summary(tmp_path: Path) -> None:
    path = tmp_path / "eval.json"
    path.write_text(
        json.dumps(
            {
                "total": 2,
                "passed": 1,
                "results": [
                    {"name": "ok", "passed": True},
                    {"name": "bad", "passed": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    text = render_markdown(path)
    assert "Agent Eval" in text
    assert "1/2" in text
    assert "bad" in text
