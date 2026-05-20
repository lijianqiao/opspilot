"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: config.py
@DateTime: 2026-05-20
@Docs: Gateway provider and settings models (Pydantic / env).
    网关上游 Provider 与全局 Settings 配置模型（Pydantic / 环境变量）。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewayProvider(BaseModel):
    """One upstream LLM provider endpoint for the gateway.

    网关使用的单个上游 LLM Provider 端点配置。

    Attributes:
        name: Provider identifier used in metrics and routing.
            Provider 标识名（用于指标与路由）。
        base_url: OpenAI-compatible API base URL (no trailing slash).
            OpenAI 兼容 API 基础地址（不含尾部斜杠）。
        api_key: Bearer token for upstream authorization.
            访问上游的 Bearer API 密钥。
        enabled: Whether this provider participates in routing.
            是否参与路由选择。
    """

    name: str
    base_url: str
    api_key: str = "sk-local"
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        """Normalize base_url by removing a trailing slash.

        规范化 base_url：去除尾部斜杠。

        Args:
            value: Raw base URL string.
                原始基础 URL 字符串。

        Returns:
            Base URL without trailing slash.
                不含尾部斜杠的基础 URL。
        """
        return value.rstrip("/")


class GatewaySettings(BaseSettings):
    """Gateway runtime settings from OPSPILOT_GATEWAY_* environment variables.

    网关运行时配置：通过 OPSPILOT_GATEWAY_ 前缀环境变量注入。

    Attributes:
        providers: Ordered list of upstream providers (JSON or list).
            有序上游 Provider 列表（支持 JSON 字符串或列表）。
        redis_url: Redis URL for distributed rate limiting.
            分布式限流使用的 Redis 连接地址。
        requests_per_minute: Per-client fixed-window request cap.
            每客户端固定窗口内的请求上限。
        provider_timeout_seconds: Upstream HTTP timeout in seconds.
            访问上游的 HTTP 超时时间（秒）。
        auth_token: Gateway Bearer token (empty = fail-closed 503).
            网关 Bearer 令牌（空则 fail-closed 返回 503）。
    """

    model_config = SettingsConfigDict(env_prefix="OPSPILOT_GATEWAY_", env_file=".env", extra="ignore")

    providers: list[GatewayProvider] = Field(
        default_factory=lambda: [GatewayProvider(name="local", base_url="http://localhost:8080/v1", api_key="sk-local")]
    )
    redis_url: str = "redis://localhost:6379/0"
    requests_per_minute: int = 60
    provider_timeout_seconds: float = 120.0
    # 网关 Bearer 鉴权：未配置则 fail-closed（503），避免裸奔成开放代理可盗刷上游 key
    auth_token: str = Field(default="", repr=False)

    @field_validator("providers", mode="before")
    @classmethod
    def parse_providers(cls, value: Any) -> Any:
        """Parse providers from JSON string when loaded from environment.

        从环境变量加载时，将 JSON 字符串解析为 Provider 列表。

        Args:
            value: List of providers or JSON-encoded string.
                Provider 列表或 JSON 编码字符串。

        Returns:
            Parsed provider list or original value for Pydantic to coerce.
                解析后的列表，或交由 Pydantic 继续转换的原始值。
        """
        if isinstance(value, str):
            return json.loads(value)
        return value
