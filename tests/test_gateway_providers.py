"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_gateway_providers.py
@DateTime: 2026-05-20
@Docs: Tests ProviderRouter primary/fallback selection.
    测试 ProviderRouter 主备切换。
"""

from opspilot.gateway.config import GatewayProvider
from opspilot.gateway.providers import ProviderRouter


def test_selects_first_enabled_provider() -> None:
    router = ProviderRouter(
        [
            GatewayProvider(name="disabled", base_url="http://disabled/v1", api_key="x", enabled=False),
            GatewayProvider(name="local", base_url="http://localhost:8080/v1", api_key="sk-local"),
        ]
    )
    assert router.select().name == "local"


def test_fallback_returns_next_enabled_provider() -> None:
    first = GatewayProvider(name="local", base_url="http://localhost:8080/v1", api_key="sk-local")
    second = GatewayProvider(name="backup", base_url="https://example.test/v1", api_key="sk-backup")
    router = ProviderRouter([first, second])
    fallback = router.fallback_after(first)
    assert fallback is not None
    assert fallback.name == "backup"


def test_fallback_returns_none_when_no_next_provider() -> None:
    provider = GatewayProvider(name="local", base_url="http://localhost:8080/v1", api_key="sk-local")
    router = ProviderRouter([provider])
    assert router.fallback_after(provider) is None
