"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-05-20
@Docs: Actions package: pluggable ops backend executors (mock by default).
    Actions 包：可插拔的运维后端执行器（默认 mock 实现）。
"""

from opspilot.actions.mock_executor import remediation_mock, restart_service_mock, scale_service_mock

__all__ = ["remediation_mock", "restart_service_mock", "scale_service_mock"]
