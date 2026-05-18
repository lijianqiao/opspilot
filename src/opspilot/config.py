from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_", env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "qwen3.5-9b"
    llm_api_key: str = "sk-local"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    agent_max_tool_calls: int = 8
    pg_dsn: str = "postgresql://opspilot:opspilot@localhost:5432/opspilot"


def get_settings() -> Settings:
    return Settings()
