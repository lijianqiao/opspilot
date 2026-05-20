"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: providers.py
@DateTime: 2026-05-20
@Docs: Provider selection and ordered fallback routing for the gateway.
    网关上游 Provider 按配置顺序选择与有序降级路由。
"""

from __future__ import annotations

from opspilot.gateway.config import GatewayProvider


class ProviderRouter:
    """Selects enabled providers in configured order and supplies fallbacks.

    按配置顺序选择已启用的 Provider，并在失败时提供下一个备选。

    Args:
        providers: Full provider list from settings (enabled entries only kept).
            来自配置的全部 Provider 列表（仅保留 enabled=True 的项）。
    """

    def __init__(self, providers: list[GatewayProvider]) -> None:
        self._providers = [provider for provider in providers if provider.enabled]
        if not self._providers:
            raise ValueError("At least one enabled gateway provider is required")

    def select(self) -> GatewayProvider:
        """Return the primary (first enabled) provider.

        返回主用（第一个已启用）Provider。

        Returns:
            Primary gateway provider.
                主用网关 Provider。
        """
        return self._providers[0]

    def fallback_after(self, provider: GatewayProvider) -> GatewayProvider | None:
        """Return the next enabled provider after the given one, if any.

        返回给定 Provider 之后的下一个已启用 Provider；若无则返回 None。

        Args:
            provider: Provider that was just attempted.
                刚尝试过的 Provider。

        Returns:
            Next provider in order, or None when no fallback remains.
                顺序中的下一个 Provider；无备选时返回 None。
        """
        for index, current in enumerate(self._providers):
            if current.name == provider.name:
                next_index = index + 1
                if next_index < len(self._providers):
                    return self._providers[next_index]
                return None
        return None
