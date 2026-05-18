import pytest

from opspilot.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear env vars so we test actual defaults, not .env overrides
    for key in ("OPSPILOT_LLM_BASE_URL", "OPSPILOT_LLM_MODEL", "OPSPILOT_PG_DSN"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_base_url == "http://localhost:8080/v1"
    assert s.llm_model == "qwen3.5-9b"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_LLM_MODEL", "custom-model")
    assert Settings().llm_model == "custom-model"


def test_get_settings_returns_settings() -> None:
    assert isinstance(get_settings(), Settings)


def test_settings_stage2_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPSPILOT_PG_DSN", raising=False)
    monkeypatch.delenv("OPSPILOT_AGENT_MAX_TOOL_CALLS", raising=False)
    s = Settings(_env_file=None)
    assert s.agent_max_tool_calls == 8
    assert s.pg_dsn == "postgresql://opspilot:opspilot@localhost:5432/opspilot"


def test_settings_stage2_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_AGENT_MAX_TOOL_CALLS", "3")
    assert Settings().agent_max_tool_calls == 3
