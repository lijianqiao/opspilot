from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_", env_file=".env", extra="ignore")

    # repr=False 的字段为敏感信息：不进 repr/str，避免日志、pytest 断言、异常回显泄露密钥
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "qwen3.5-9b"
    llm_api_key: str = Field(default="sk-local", repr=False)
    feishu_app_id: str = ""
    feishu_app_secret: str = Field(default="", repr=False)
    feishu_verification_token: str = Field(default="", repr=False)
    feishu_encrypt_key: str = Field(default="", repr=False)
    agent_max_tool_calls: int = 8
    pg_dsn: str = Field(default="postgresql://opspilot:opspilot@localhost:5432/opspilot", repr=False)
    # Phase 1/2/5 新增项（先占位，后续任务使用）
    audit_log_path: str = "logs/opspilot_audit.jsonl"
    confirm_ttl_seconds: int = 300
    api_auth_token: str = Field(default="", repr=False)  # 为空表示未配置鉴权（端点 fail-closed）
    alertmanager_hmac_secret: str = Field(default="", repr=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
