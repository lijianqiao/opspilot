from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_", env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "qwen3.5-9b"
    llm_api_key: str = "sk-local"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    agent_max_tool_calls: int = 8
    pg_dsn: str = "postgresql://opspilot:opspilot@localhost:5432/opspilot"
    # Phase 1/2/5 新增项（先占位，后续任务使用）
    audit_log_path: str = "logs/opspilot_audit.jsonl"
    confirm_ttl_seconds: int = 300
    api_auth_token: str = ""  # 为空表示未配置鉴权（端点 fail-closed）
    alertmanager_hmac_secret: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
