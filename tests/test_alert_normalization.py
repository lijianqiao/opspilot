"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_alert_normalization.py
@DateTime: 2026-05-20
@Docs: Tests multi-source alert payload normalization adapters.
    测试多来源告警载荷归一化适配器。
"""

from __future__ import annotations

from opspilot.alerts.adapters import normalize_alert_payload


def test_normalize_alertmanager_payload() -> None:
    """
    Verify alertmanager payloads map labels/annotations into a NormalizedAlert.

    验证：Alertmanager 载荷的 labels/annotations 能正确归一化。
    """
    event = normalize_alert_payload(
        {
            "alerts": [
                {
                    "labels": {
                        "alertname": "PodOOM",
                        "service": "user-service",
                        "namespace": "prod",
                        "severity": "critical",
                    },
                    "annotations": {"summary": "OOM spike", "description": "pods killed"},
                    "startsAt": "2026-05-20T02:00:00Z",
                }
            ]
        },
        source="alertmanager",
    )
    assert event.source == "alertmanager"
    assert event.alerts[0].service == "user-service"
    assert event.alerts[0].environment == "prod"
    assert event.alerts[0].alertname == "PodOOM"
    assert event.alerts[0].severity == "critical"


def test_normalize_grafana_payload() -> None:
    """
    Verify grafana payloads use ruleName/tags as the normalized source.

    验证：Grafana 载荷使用 ruleName 与 tags 作为归一化来源。
    """
    event = normalize_alert_payload(
        {
            "title": "High memory",
            "state": "alerting",
            "ruleName": "MemoryHigh",
            "tags": {"service": "payment", "env": "prod"},
            "message": "memory over threshold",
        },
        source="grafana",
    )
    assert event.source == "grafana"
    assert event.alerts[0].alertname == "MemoryHigh"
    assert event.alerts[0].service == "payment"
    assert event.alerts[0].environment == "prod"


def test_normalize_zabbix_payload() -> None:
    """
    Verify zabbix payloads expose trigger/host/severity.

    验证：Zabbix 载荷暴露 trigger/host/severity 字段。
    """
    event = normalize_alert_payload(
        {
            "trigger": "CPU high",
            "host": "api-01",
            "severity": "High",
            "service": "api",
            "env": "prod",
        },
        source="zabbix",
    )
    assert event.source == "zabbix"
    assert event.alerts[0].source_entity == "api-01"
    assert event.alerts[0].severity == "high"
    assert event.alerts[0].service == "api"


def test_normalize_empty_alertmanager_payload_keeps_unknown_fallback() -> None:
    """
    Verify empty alertmanager payload yields a single 'unknown' fallback alert.

    验证：Alertmanager 空载荷会构造一个 "unknown" 兜底告警。
    """
    event = normalize_alert_payload({"alerts": []}, source="alertmanager")
    assert len(event.alerts) == 1
    assert event.alerts[0].alertname == "unknown"
    assert event.alerts[0].severity == "warning"
    assert event.alerts[0].service == "unknown"


def test_normalize_unknown_source_falls_back_to_generic() -> None:
    """
    Verify an unknown source uses the generic adapter and preserves payload.

    验证：未知 source 走通用适配器并保留原始 payload。
    """
    event = normalize_alert_payload(
        {"alertname": "Disk", "service": "db", "severity": "warning"},
        source="custom",
    )
    assert event.source == "custom"
    assert event.alerts[0].alertname == "Disk"
    assert event.alerts[0].service == "db"
