"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: adapters.py
@DateTime: 2026-05-20
@Docs: Source-specific adapters that map raw webhook payloads to NormalizedAlertEvent.
    将各告警来源原始 Webhook 载荷映射为 NormalizedAlertEvent 的适配器。
"""

from __future__ import annotations

from typing import Any

from opspilot.alerts.models import NormalizedAlert, NormalizedAlertEvent


def _text(value: Any, default: str = "") -> str:
    """Coerce value to non-empty text or fall back to default.

    将任意值转换为非空字符串，空值时回退到 default。
    """
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _lower(value: Any, default: str = "warning") -> str:
    """Lower-case string with default fallback when blank.

    将值转为小写字符串；为空时回退到 default。
    """
    text = _text(value, "").strip().lower()
    return text or default


def normalize_alert_payload(payload: dict[str, Any], source: str = "alertmanager") -> NormalizedAlertEvent:
    """Dispatch a raw alert payload to the matching source adapter.

    根据 source 选择对应适配器，将原始告警载荷归一化为 NormalizedAlertEvent。

    Args:
        payload: Raw JSON dict received from the upstream alert source.
            来自上游告警源的原始 JSON 字典。
        source: Source identifier (e.g. alertmanager/grafana/zabbix).
            告警来源标识（如 alertmanager/grafana/zabbix）。

    Returns:
        NormalizedAlertEvent containing one or more NormalizedAlert items.
            含一个或多个 NormalizedAlert 的归一化事件。
    """
    source_key = (source or payload.get("source") or "alertmanager")
    source_key = str(source_key).strip().lower()
    if source_key == "alertmanager":
        return _from_alertmanager(payload)
    if source_key == "grafana":
        return _from_grafana(payload)
    if source_key == "zabbix":
        return _from_zabbix(payload)
    return _from_generic(payload, source_key)


def _from_alertmanager(payload: dict[str, Any]) -> NormalizedAlertEvent:
    """Adapt an Alertmanager webhook body.

    适配 Alertmanager Webhook 载荷。
    """
    alerts: list[NormalizedAlert] = []
    for item in payload.get("alerts", []):
        if not isinstance(item, dict):
            continue
        raw_labels = item.get("labels", {})
        labels = raw_labels if isinstance(raw_labels, dict) else {}
        raw_annotations = item.get("annotations", {})
        annotations = raw_annotations if isinstance(raw_annotations, dict) else {}
        alerts.append(
            NormalizedAlert(
                source="alertmanager",
                alertname=_text(labels.get("alertname"), "unknown"),
                severity=_lower(labels.get("severity")),
                service=_text(labels.get("service"), "unknown"),
                environment=_text(labels.get("namespace") or labels.get("env"), "default"),
                source_entity=_text(labels.get("pod") or labels.get("instance"), "unknown"),
                summary=_text(annotations.get("summary")),
                description=_text(annotations.get("description")),
                starts_at=_text(item.get("startsAt"), "") or None,
                labels=labels,
                annotations=annotations,
                raw_payload=item,
            )
        )
    if not alerts:
        alerts.append(NormalizedAlert(source="alertmanager", raw_payload=payload))
    return NormalizedAlertEvent(source="alertmanager", alerts=alerts, raw_payload=payload)


def _from_grafana(payload: dict[str, Any]) -> NormalizedAlertEvent:
    """Adapt a Grafana unified-alerting webhook body.

    适配 Grafana 统一告警 Webhook 载荷。
    """
    raw_tags = payload.get("tags", {})
    tags = raw_tags if isinstance(raw_tags, dict) else {}
    alert = NormalizedAlert(
        source="grafana",
        alertname=_text(payload.get("ruleName") or payload.get("title"), "unknown"),
        severity=_lower(tags.get("severity") or payload.get("state")),
        service=_text(tags.get("service"), "unknown"),
        environment=_text(tags.get("env") or tags.get("namespace"), "default"),
        source_entity=_text(tags.get("instance") or tags.get("host"), "unknown"),
        summary=_text(payload.get("title")),
        description=_text(payload.get("message")),
        labels=tags,
        raw_payload=payload,
    )
    return NormalizedAlertEvent(source="grafana", alerts=[alert], raw_payload=payload)


def _from_zabbix(payload: dict[str, Any]) -> NormalizedAlertEvent:
    """Adapt a Zabbix webhook body.

    适配 Zabbix Webhook 载荷。
    """
    alert = NormalizedAlert(
        source="zabbix",
        alertname=_text(payload.get("trigger") or payload.get("event_name"), "unknown"),
        severity=_lower(payload.get("severity")),
        service=_text(payload.get("service"), "unknown"),
        environment=_text(payload.get("env") or payload.get("namespace"), "default"),
        source_entity=_text(payload.get("host") or payload.get("hostname"), "unknown"),
        summary=_text(payload.get("trigger") or payload.get("event_name")),
        description=_text(payload.get("description") or payload.get("message")),
        raw_payload=payload,
    )
    return NormalizedAlertEvent(source="zabbix", alerts=[alert], raw_payload=payload)


def _from_generic(payload: dict[str, Any], source: str) -> NormalizedAlertEvent:
    """Adapt an unknown source via best-effort field mapping.

    针对未知来源进行尽力而为的字段映射。
    """
    alert = NormalizedAlert(
        source=source,
        alertname=_text(payload.get("alertname") or payload.get("title"), "unknown"),
        severity=_lower(payload.get("severity")),
        service=_text(payload.get("service"), "unknown"),
        environment=_text(payload.get("env") or payload.get("namespace"), "default"),
        summary=_text(payload.get("summary")),
        description=_text(payload.get("description") or payload.get("message")),
        raw_payload=payload,
    )
    return NormalizedAlertEvent(source=source, alerts=[alert], raw_payload=payload)
