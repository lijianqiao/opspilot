from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewayProvider(BaseModel):
    name: str
    base_url: str
    api_key: str = "sk-local"
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_GATEWAY_", env_file=".env", extra="ignore")

    providers: list[GatewayProvider] = Field(
        default_factory=lambda: [
            GatewayProvider(name="local", base_url="http://localhost:8080/v1", api_key="sk-local")
        ]
    )
    redis_url: str = "redis://localhost:6379/0"
    requests_per_minute: int = 60
    provider_timeout_seconds: float = 120.0

    @field_validator("providers", mode="before")
    @classmethod
    def parse_providers(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value
