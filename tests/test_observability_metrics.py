from opspilot.observability.metrics import (
    record_agent_request,
    record_guardrail_block,
    record_llm_call,
    record_tool_call,
    render_metrics,
)


def test_metrics_render_prometheus_text() -> None:
    record_agent_request(endpoint="/ask", status="success")
    record_tool_call(tool="kubectl_get", status="success", duration_seconds=0.01)
    record_guardrail_block(tool="kubectl_scale")
    record_llm_call(provider="local", status="success", duration_seconds=0.01, token_estimate=12)
    text = render_metrics().decode()
    assert "opspilot_agent_requests_total" in text
    assert "opspilot_tool_calls_total" in text
    assert "opspilot_guardrail_blocks_total" in text
    assert "opspilot_llm_tokens_estimated_total" in text
