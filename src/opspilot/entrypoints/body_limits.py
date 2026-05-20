"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: body_limits.py
@DateTime: 2026-05-20
@Docs: Shared request body size guards for HTTP entrypoints.
    共享 HTTP 入口的请求体大小限制。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

MAX_AGENT_BODY_BYTES = 512_000
MAX_AGENT_QUESTION_CHARS = 4000
MAX_ALERT_BODY_BYTES = 512_000
MAX_GATEWAY_BODY_BYTES = 1_000_000
MAX_GATEWAY_CONTENT_CHARS = 200_000


def too_large_response() -> JSONResponse:
    """Return a JSON response for payload too large.
    返回请求体过大的 JSON 响应。
    """
    return JSONResponse({"detail": "payload too large"}, status_code=413)


def content_length_exceeds(request: Request, limit: int) -> bool:
    """Check if the content length exceeds the limit.
    检查请求体长度是否超过限制。
    """
    raw = request.headers.get("content-length")
    if raw is None:
        return False
    try:
        return int(raw) > limit
    except ValueError:
        return False


async def read_limited_body(request: Request, limit: int) -> bytes:
    """Read a limited body from the request.
    从请求中读取限制大小的请求体。

    Args:
        request: Incoming HTTP request.
            入站 HTTP 请求。
        limit: Maximum body size in bytes.
            最大请求体大小（字节）。

    Returns:
        Bytes of the limited body.
            限制大小的请求体字节。

    Raises:
        HTTPException: 413 if the body is too large.
            请求体过大时 413。
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="payload too large")
        chunks.append(chunk)
    return b"".join(chunks)


async def read_limited_json(request: Request, limit: int) -> Any:
    """Read a limited JSON body from the request.
    从请求中读取限制大小的 JSON 请求体。

    Args:
        request: Incoming HTTP request.
            入站 HTTP 请求。
        limit: Maximum body size in bytes.
            最大请求体大小（字节）。

    Returns:
        JSON object of the limited body.
            限制大小的请求体 JSON 对象。

    Raises:
        HTTPException: 400 if the body is not valid JSON, 413 if the body is too large.
            请求体不是有效 JSON 时 400，请求体过大时 413。
    """
    raw = await read_limited_body(request, limit)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc


def require_json_object(payload: Any) -> dict[str, Any]:
    """Require a top-level JSON object.
    要求顶层 JSON 对象。

    Args:
        payload: Payload to check.
            要检查的载荷。

    Returns:
        JSON object.
            顶层 JSON 对象。

    Raises:
        HTTPException: 422 if the payload is not a JSON object.
            载荷不是 JSON 对象时 422。
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="json object is required")
    return payload


def require_alertmanager_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Require an Alertmanager-shaped webhook payload.

    校验 Alertmanager Webhook 载荷结构，避免 handler 崩溃。

    Args:
        payload: Parsed JSON object from /alert body.
            来自 /alert 请求体的已解析 JSON 对象。

    Returns:
        The same dict if validation passes.
            校验通过时返回原字典。

    Raises:
        HTTPException: 422 when alerts is missing or not a list of objects.
            alerts 缺失或不是对象列表时返回 422。
    """
    alerts = payload.get("alerts", [])
    if not isinstance(alerts, list) or any(not isinstance(alert, dict) for alert in alerts):
        raise HTTPException(status_code=422, detail="alerts must be a list of objects")
    return payload
