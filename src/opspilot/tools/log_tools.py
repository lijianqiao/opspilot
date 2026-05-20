"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: log_tools.py
@DateTime: 2026-05-20
@Docs: Log analysis tools (mock) for the Log Analyzer agent.
    日志分析工具（模拟），供日志分析智能体使用。
"""

from opspilot.tools.registry import register_tool


@register_tool
def aggregate_errors(service: str, namespace: str = "default") -> str:
    """Aggregate error logs for a service grouped by error type.
    聚合指定服务的错误日志，返回按错误类型分组的统计。

    Args:
        service: Service name to aggregate errors for.
            要聚合错误的服务名称。
        namespace: Kubernetes namespace of the service.
            服务所在的 Kubernetes 命名空间。

    Returns:
        Mock aggregation summary with counts and suggestions.
            模拟的错误聚合摘要（含次数与建议）。
    """
    return (
        f"[{namespace}/{service}] 错误日志聚合（最近1小时）：\n"
        f"  NullPointerException: 23 次\n"
        f"  ConnectionTimeout: 15 次\n"
        f"  IllegalStateException: 8 次\n"
        f"  OOMKilled: 1 次\n"
        f"建议：优先排查 NullPointerException，最近 10 分钟集中在 "
        f"/api/orders 端点。"
    )


@register_tool
def tail_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 50) -> str:
    """Return the tail of recent logs for a pod.
    获取指定 Pod 最近的日志末尾内容。

    Args:
        pod_name: Pod name to tail logs from.
            要拉取日志的 Pod 名称。
        namespace: Pod namespace.
            Pod 所在命名空间。
        tail_lines: Number of recent lines to include (mock).
            包含的最近日志行数（模拟）。

    Returns:
        Mock multi-line log tail text.
            模拟的多行日志尾部文本。
    """
    return (
        f"[{namespace}/{pod_name}] 最近 {tail_lines} 行日志：\n"
        f"2026-05-18T07:59:01Z INFO  OrderService - 处理订单 #12345\n"
        f"2026-05-18T07:59:02Z INFO  OrderService - 查询库存 SKU=ABC-001\n"
        f"2026-05-18T07:59:03Z WARN  OrderService - 库存服务响应超时 (retry 1/3)\n"
        f"2026-05-18T07:59:04Z WARN  OrderService - 库存服务响应超时 (retry 2/3)\n"
        f"2026-05-18T07:59:05Z ERROR OrderService - 库存服务不可达 after 3 retries\n"
        f"2026-05-18T07:59:05Z INFO  OrderService - 订单 #12345 失败，写入 DLQ\n"
        f"... (省略中间行)\n"
        f"2026-05-18T08:00:00Z FATAL JVM - OutOfMemoryError: Java heap space\n"
        f"2026-05-18T08:00:01Z INFO  K8s - OOMKilled, exit code 137"
    )
