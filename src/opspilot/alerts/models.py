"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: models.py
@DateTime: 2026-05-20
@Docs: Normalized alert Pydantic models shared by all source adapters.
    所有告警来源适配器共享的归一化 Pydantic 模型。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedAlert(BaseModel):
    """Single normalized alert across all supported sources.

    统一封装的单条告警（兼容多来源）。
    """

    source: str
    alertname: str = "unknown"
    severity: str = "warning"
    service: str = "unknown"
    environment: str = "default"
    source_entity: str = "unknown"
    summary: str = ""
    description: str = ""
    starts_at: str | None = None
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedAlertEvent(BaseModel):
    """Envelope grouping one or more normalized alerts from a single source.

    将来自同一来源的一组归一化告警封装为事件信封。
    """

    source: str
    alerts: list[NormalizedAlert]
    raw_payload: dict[str, Any] = Field(default_factory=dict)
