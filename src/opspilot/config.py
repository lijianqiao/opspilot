"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: config.py
@DateTime: 2026-05-20
@Docs: Application settings loaded from environment variables.
    应用配置：从环境变量加载的运行时设置。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from OPSPILOT_* environment variables.

    应用配置：通过 OPSPILOT_ 前缀环境变量注入。

    Attributes:
        llm_base_url: OpenAI-compatible API base URL.
            LLM 服务基础地址。
        llm_model: Model name for chat completions.
            对话补全使用的模型名。
        llm_api_key: API key (sensitive, excluded from repr).
            API 密钥（敏感字段，不出现在 repr 中）。
        feishu_app_id: Feishu application ID.
            飞书应用 App ID。
        feishu_app_secret: Feishu app secret (sensitive).
            飞书应用密钥（敏感字段）。
        feishu_verification_token: Feishu event verification token.
            飞书事件订阅校验 Token。
        feishu_encrypt_key: Feishu event encryption key.
            飞书事件加密密钥。
        agent_max_tool_calls: Maximum tool invocations per agent run.
            单次 Agent 运行允许的最大工具调用次数。
        pg_dsn: PostgreSQL connection string (sensitive).
            PostgreSQL 连接串（敏感字段）。
        audit_log_path: Path to JSONL audit log file.
            审计日志 JSONL 文件路径。
        confirm_ttl_seconds: TTL for danger-op confirmation tokens.
            危险操作确认令牌的有效期（秒）。
        api_auth_token: Bearer token for HTTP API (empty = unconfigured).
            HTTP API Bearer 令牌（空表示未配置，端点 fail-closed）。
        alertmanager_hmac_secret: HMAC secret for Alertmanager webhooks.
            Alertmanager Webhook HMAC 密钥。
        agent_core_url: Base URL for channel adapters to call agent-core HTTP API.
            渠道适配器调用 agent-core 的 HTTP 基址。
    """

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
    agent_core_url: str = "http://localhost:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    返回缓存的 Settings 单例实例。

    Returns:
        Loaded Settings instance.
            已加载的配置实例。
    """
    return Settings()
