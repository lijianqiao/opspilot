"""Log analysis tools — mock implementations backed by fixtures.

Stage 3: Log Analyzer Agent tools. Mock data that looks like real
Loki / container log output. Registered via @register_tool.
"""

from opspilot.tools.registry import register_tool


@register_tool
def aggregate_errors(service: str, namespace: str = "default") -> str:
    """聚合指定服务的错误日志，返回按错误类型分组的统计。"""
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
    """获取指定 Pod 最近的日志末尾内容。"""
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
