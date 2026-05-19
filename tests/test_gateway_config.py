import pytest

from opspilot.gateway.config import GatewayProvider, GatewaySettings


def test_default_gateway_provider_uses_existing_llama_cpp_defaults() -> None:
    settings = GatewaySettings()
    assert len(settings.providers) == 1
    provider = settings.providers[0]
    assert provider.name == "local"
    assert provider.base_url == "http://localhost:8080/v1"
    assert provider.api_key == "sk-local"


def test_provider_list_parses_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "OPSPILOT_GATEWAY_PROVIDERS",
        '[{"name":"local","base_url":"http://localhost:8080/v1","api_key":"sk-local"},'
        '{"name":"backup","base_url":"https://example.test/v1","api_key":"sk-backup"}]',
    )
    settings = GatewaySettings()
    assert [p.name for p in settings.providers] == ["local", "backup"]


def test_provider_base_url_has_no_trailing_slash() -> None:
    provider = GatewayProvider(name="x", base_url="http://localhost:8080/v1/", api_key="k")
    assert provider.base_url == "http://localhost:8080/v1"
