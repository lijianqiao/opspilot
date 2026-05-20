"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-05-20
@Docs: Unified alert models package — re-exports normalized models.
    统一告警模型包：导出归一化模型。
"""

from opspilot.alerts.models import NormalizedAlert, NormalizedAlertEvent

__all__ = ["NormalizedAlert", "NormalizedAlertEvent"]
