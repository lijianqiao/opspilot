from __future__ import annotations

from opspilot.gateway.config import GatewayProvider


class ProviderRouter:
    """Selects enabled providers in configured order."""

    def __init__(self, providers: list[GatewayProvider]) -> None:
        self._providers = [provider for provider in providers if provider.enabled]
        if not self._providers:
            raise ValueError("At least one enabled gateway provider is required")

    def select(self) -> GatewayProvider:
        return self._providers[0]

    def fallback_after(self, provider: GatewayProvider) -> GatewayProvider | None:
        for index, current in enumerate(self._providers):
            if current.name == provider.name:
                next_index = index + 1
                if next_index < len(self._providers):
                    return self._providers[next_index]
                return None
        return None
