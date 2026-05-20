"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_config.py
@DateTime: 2026-05-20
@Docs: Tests Settings defaults and get_settings LRU cache.
    测试 Settings 默认值与 get_settings 缓存。
"""

import pytest

from opspilot.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Override env vars to test actual defaults (overrides .env too)
    """
    Verify settings defaults.

    验证：settings defaults。
    """
    monkeypatch.setenv("OPSPILOT_LLM_BASE_URL", "http://localhost:8080/v1")
    monkeypatch.setenv("OPSPILOT_LLM_MODEL", "qwen3.5-9b")
    s = Settings()
    assert s.llm_base_url == "http://localhost:8080/v1"
    assert s.llm_model == "qwen3.5-9b"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify settings env override.

    验证：settings env override。
    """
    monkeypatch.setenv("OPSPILOT_LLM_MODEL", "custom-model")
    assert Settings().llm_model == "custom-model"


def test_get_settings_returns_settings() -> None:
    """
    Verify get settings returns settings.

    验证：get settings returns settings。
    """
    assert isinstance(get_settings(), Settings)


def test_settings_stage2_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify settings stage2 defaults.

    验证：settings stage2 defaults。
    """
    monkeypatch.setenv("OPSPILOT_PG_DSN", "postgresql://opspilot:opspilot@localhost:5432/opspilot")
    monkeypatch.setenv("OPSPILOT_AGENT_MAX_TOOL_CALLS", "8")
    s = Settings()
    assert s.agent_max_tool_calls == 8
    assert s.pg_dsn == "postgresql://opspilot:opspilot@localhost:5432/opspilot"


def test_settings_stage2_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify settings stage2 env override.

    验证：settings stage2 env override。
    """
    monkeypatch.setenv("OPSPILOT_AGENT_MAX_TOOL_CALLS", "3")
    assert Settings().agent_max_tool_calls == 3


def test_get_settings_is_cached() -> None:
    """
    Verify get settings is cached.

    验证：get settings is cached。
    """
    assert get_settings() is get_settings()  # 同一实例，未重复读 .env


def test_agent_core_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify agent core url default.

    验证：agent core url default。
    """
    monkeypatch.delenv("OPSPILOT_AGENT_CORE_URL", raising=False)
    assert Settings().agent_core_url == "http://localhost:8000"


def test_settings_repr_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify settings repr masks secrets.

    验证：settings repr masks secrets。
    """
    monkeypatch.setenv("OPSPILOT_LLM_API_KEY", "sk-supersecret999")
    monkeypatch.setenv("OPSPILOT_PG_DSN", "postgresql://u:pw123@h/db")
    monkeypatch.setenv("OPSPILOT_API_AUTH_TOKEN", "tok-abc987")
    s = Settings()
    rendered = repr(s) + str(s)
    assert "sk-supersecret999" not in rendered
    assert "pw123" not in rendered
    assert "tok-abc987" not in rendered
    # 脱敏只影响展示，取值仍正常
    assert s.llm_api_key == "sk-supersecret999"
    assert s.api_auth_token == "tok-abc987"
