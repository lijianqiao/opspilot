"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: metrics.py
@DateTime: 2026-05-20
@Docs: Prometheus metrics for agent API, tools, guardrails, and LLM calls.
    Agent API、工具、护栏与 LLM 调用的 Prometheus 指标与记录函数。
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

AGENT_REQUESTS = Counter(
    "opspilot_agent_requests_total",
    "Total agent API requests",
    ["endpoint", "status"],
    registry=REGISTRY,
)
TOOL_CALLS = Counter(
    "opspilot_tool_calls_total",
    "Total tool calls",
    ["tool", "status"],
    registry=REGISTRY,
)
TOOL_LATENCY = Histogram(
    "opspilot_tool_call_seconds",
    "Tool call duration",
    ["tool"],
    registry=REGISTRY,
)
GUARDRAIL_BLOCKS = Counter(
    "opspilot_guardrail_blocks_total",
    "Dangerous operations blocked by guardrails",
    ["tool"],
    registry=REGISTRY,
)
LLM_CALLS = Counter(
    "opspilot_llm_calls_total",
    "Total LLM calls",
    ["provider", "status"],
    registry=REGISTRY,
)
LLM_LATENCY = Histogram(
    "opspilot_llm_call_seconds",
    "LLM call duration",
    ["provider"],
    registry=REGISTRY,
)
LLM_TOKENS_ESTIMATED = Counter(
    "opspilot_llm_tokens_estimated_total",
    "Rough token estimate based on message/response text length",
    ["provider"],
    registry=REGISTRY,
)


def record_agent_request(endpoint: str, status: str) -> None:
    """Increment agent HTTP request counter.

    递增 Agent HTTP 请求计数。

    Args:
        endpoint: Route or handler label.
            路由或处理端点标签。
        status: HTTP or logical status label.
            HTTP 或逻辑状态标签。
    """
    AGENT_REQUESTS.labels(endpoint=endpoint, status=status).inc()


def record_tool_call(tool: str, status: str, duration_seconds: float) -> None:
    """Record a tool invocation count and latency observation.

    记录工具调用次数与延迟观测值。

    Args:
        tool: Tool name label.
            工具名称标签。
        status: Outcome status label.
            结果状态标签。
        duration_seconds: Wall-clock duration in seconds.
            墙钟耗时（秒）。
    """
    TOOL_CALLS.labels(tool=tool, status=status).inc()
    TOOL_LATENCY.labels(tool=tool).observe(duration_seconds)


def record_guardrail_block(tool: str) -> None:
    """Increment counter when a dangerous tool is blocked by guardrails.

    当护栏拦截危险工具时递增计数。

    Args:
        tool: Blocked tool name.
            被拦截的工具名称。
    """
    GUARDRAIL_BLOCKS.labels(tool=tool).inc()


def record_llm_call(provider: str, status: str, duration_seconds: float, token_estimate: int) -> None:
    """Record LLM call count, latency, and rough token estimate.

    记录 LLM 调用次数、延迟与粗略 token 估算增量。

    Args:
        provider: LLM provider label.
            LLM 提供方标签。
        status: Outcome status label.
            结果状态标签。
        duration_seconds: Call duration in seconds.
            调用耗时（秒）。
        token_estimate: Rough token count delta to add.
            粗略 token 增量估算。
    """
    LLM_CALLS.labels(provider=provider, status=status).inc()
    LLM_LATENCY.labels(provider=provider).observe(duration_seconds)
    LLM_TOKENS_ESTIMATED.labels(provider=provider).inc(token_estimate)


def render_metrics() -> bytes:
    """Export all observability metrics in Prometheus text format.

    以 Prometheus 文本格式导出全部可观测性指标。

    Returns:
        Prometheus exposition format bytes.
            Prometheus 文本 exposition 格式字节串。
    """
    return generate_latest(REGISTRY)
