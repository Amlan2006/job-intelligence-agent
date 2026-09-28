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
    groq_chat_url: str = "https://api.groq.com/openai/v1/chat/completions"
    tavily_search_url: str = "https://api.tavily.com/search"
    defillama_pro_base_url: str = "https://pro-api.llama.fi"
    defillama_protocols_url: str = "https://api.llama.fi/protocols"
    defillama_raises_url: str = "https://defillama.com/raises"
    groq_timeout_seconds: float = Field(default=30, gt=0)
    log_level: str = "INFO"
    tavily_api_key: SecretStr = SecretStr("")
    research_timeout_seconds: float = Field(default=240, gt=0)
    company_score_weights: dict[str, int] = Field(default_factory=dict)
    resume_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    resume_max_pages: int = Field(default=20, gt=0)
    resume_max_characters: int = Field(default=50000, gt=0)
    resume_parse_timeout_seconds: float = Field(default=15, gt=0)
    resume_analysis_timeout_seconds: float = Field(default=180, gt=0)
    opportunity_timeout_seconds: float = Field(default=360, gt=0)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = ".cache/embeddings"
    embedding_timeout_seconds: float = Field(default=60, gt=0)
    semantic_match_threshold: float = Field(default=0.88, gt=0, le=1)
    contact_limit: int = Field(default=10, ge=1, le=10)
    contact_timeout_seconds: float = Field(default=150, gt=0)
    outreach_timeout_seconds: float = Field(default=180, gt=0)
    defillama_api_key: SecretStr = SecretStr("")
    funding_discovery_timeout_seconds: float = Field(default=240, gt=0)
    discovery_company_timeout_seconds: float = Field(default=600, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
