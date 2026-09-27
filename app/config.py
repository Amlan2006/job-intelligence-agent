from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_agent"
    codex_executable: str = "codex"
    codex_model: str = ""
    codex_timeout_seconds: float = Field(default=120, gt=0)
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = ""
    groq_timeout_seconds: float = Field(default=30, gt=0)
    log_level: str = "INFO"
    tavily_api_key: SecretStr = SecretStr("")
    research_timeout_seconds: float = Field(default=240, gt=0)
    company_score_weights: dict[str, int] = Field(default_factory=dict)


@lru_cache
def get_settings() -> Settings:
    return Settings()
