"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_agent_init.py
@DateTime: 2026-05-20
@Docs: Tests opspilot.agent package public exports (no run_react).
    测试 opspilot.agent 包级导出（不含 run_react）。
"""


def test_run_react_not_exported_from_package() -> None:
    import opspilot.agent as agent_pkg

    assert "run_react" not in agent_pkg.__all__
    assert not hasattr(agent_pkg, "run_react")


def test_run_react_graph_still_exported() -> None:
    from opspilot.agent import run_react_graph

    assert callable(run_react_graph)
