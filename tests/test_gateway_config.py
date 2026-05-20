"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_gateway_config.py
@DateTime: 2026-05-20
@Docs: Tests GatewaySettings and provider JSON parsing.
    测试 GatewaySettings 与 provider JSON 解析。
"""

import pytest

from opspilot.gateway.config import GatewayProvider, GatewaySettings


def test_default_gateway_provider_uses_existing_llama_cpp_defaults() -> None:
    """
    Verify default gateway provider uses existing llama cpp defaults.

    验证：default gateway provider uses existing llama cpp defaults。
    """
    settings = GatewaySettings()
    assert len(settings.providers) == 1
    provider = settings.providers[0]
    assert provider.name == "local"
    assert provider.base_url == "http://localhost:8080/v1"
    assert provider.api_key == "sk-local"


def test_provider_list_parses_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify provider list parses json env.

    验证：provider list parses json env。
    """
    monkeypatch.setenv(
        "OPSPILOT_GATEWAY_PROVIDERS",
        '[{"name":"local","base_url":"http://localhost:8080/v1","api_key":"sk-local"},'
        '{"name":"backup","base_url":"https://example.test/v1","api_key":"sk-backup"}]',
    )
    settings = GatewaySettings()
    assert [p.name for p in settings.providers] == ["local", "backup"]


def test_provider_base_url_has_no_trailing_slash() -> None:
    """
    Verify provider base url has no trailing slash.

    验证：provider base url has no trailing slash。
    """
    provider = GatewayProvider(name="x", base_url="http://localhost:8080/v1/", api_key="k")
    assert provider.base_url == "http://localhost:8080/v1"
