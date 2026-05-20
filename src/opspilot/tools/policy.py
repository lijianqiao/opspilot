"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: policy.py
@DateTime: 2026-05-20
@Docs: Kubernetes tool policy for read-only access.
    Kubernetes 工具策略：只读访问。
"""

from __future__ import annotations

SENSITIVE_KUBECTL_RESOURCES = {"secret", "secrets", "configmap", "configmaps"}
SUPPORTED_KUBECTL_READ_RESOURCES = {"pod", "pods"}


def normalize_kubectl_resource(resource: str) -> str:
    """Normalize the Kubernetes resource name.
    规范化 Kubernetes 资源名称。

    Args:
        resource: Kubernetes resource name.
            Kubernetes 资源名称。

    Returns:
        Normalized Kubernetes resource name.
           规范化后的 Kubernetes 资源名称。
    """
    return resource.strip().lower()


def reject_kubectl_read_resource(resource: str) -> str | None:
    """Reject read access to sensitive Kubernetes resources.
    拒绝读取敏感 Kubernetes 资源。

    Args:
        resource: Kubernetes resource name.
            Kubernetes 资源名称。

    Returns:
        Rejection message or None if allowed.
            拒绝提示或允许时为 None。
    """
    normalized = normalize_kubectl_resource(resource)
    if normalized in SENSITIVE_KUBECTL_RESOURCES:
        return f"出于安全策略，禁止读取敏感 Kubernetes 资源：{resource}"
    if normalized not in SUPPORTED_KUBECTL_READ_RESOURCES:
        return f"暂不支持查询资源类型：{resource}"
    return None


def kubectl_describe_kind(resource: str) -> str:
    """Determine the Kubernetes resource kind for describe.
    确定 kubectl describe 使用的资源种类。

    Args:
        resource: Kubernetes resource name.
            Kubernetes 资源名称。

    Returns:
        Resource kind for describe.
            用于 describe 的资源种类。
    """
    normalized = normalize_kubectl_resource(resource)
    return "pod" if normalized == "pods" else normalized
