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
    AGENT_REQUESTS.labels(endpoint=endpoint, status=status).inc()


def record_tool_call(tool: str, status: str, duration_seconds: float) -> None:
    TOOL_CALLS.labels(tool=tool, status=status).inc()
    TOOL_LATENCY.labels(tool=tool).observe(duration_seconds)


def record_guardrail_block(tool: str) -> None:
    GUARDRAIL_BLOCKS.labels(tool=tool).inc()


def record_llm_call(provider: str, status: str, duration_seconds: float, token_estimate: int) -> None:
    LLM_CALLS.labels(provider=provider, status=status).inc()
    LLM_LATENCY.labels(provider=provider).observe(duration_seconds)
    LLM_TOKENS_ESTIMATED.labels(provider=provider).inc(token_estimate)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)
