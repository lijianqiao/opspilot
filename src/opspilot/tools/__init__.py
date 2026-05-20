"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: __init__.py
@DateTime: 2026-05-20
@Docs: Tools package public API: registry and registered tool exports.
    工具包对外 API：注册表与各已注册工具导出。
"""

from opspilot.tools.confirm import confirm_dangerous_op
from opspilot.tools.kubectl_ops import kubectl_describe, kubectl_get
from opspilot.tools.kubectl_write import kubectl_rollout_restart, kubectl_scale
from opspilot.tools.log_tools import aggregate_errors, tail_pod_logs
from opspilot.tools.pod_status import get_pod_status
from opspilot.tools.query_loki import query_loki
from opspilot.tools.query_prometheus import query_prometheus
from opspilot.tools.registry import (
    ToolInfo,
    build_tools_prompt,
    call_tool,
    get_registered_tools,
    register_tool,
)
from opspilot.tools.runbook import retrieve_runbook
from opspilot.tools.service_actions import restart_service, run_remediation, scale_service

__all__ = [
    "ToolInfo",
    "aggregate_errors",
    "build_tools_prompt",
    "call_tool",
    "confirm_dangerous_op",
    "get_registered_tools",
    "get_pod_status",
    "kubectl_describe",
    "kubectl_get",
    "kubectl_rollout_restart",
    "kubectl_scale",
    "query_loki",
    "query_prometheus",
    "register_tool",
    "restart_service",
    "retrieve_runbook",
    "run_remediation",
    "scale_service",
    "tail_pod_logs",
]
