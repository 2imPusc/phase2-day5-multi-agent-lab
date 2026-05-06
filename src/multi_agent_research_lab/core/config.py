"""Application configuration.

Keep config small and explicit. Do not read environment variables directly in agents.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load `.env` into os.environ at import time so libraries that read env vars
# directly (e.g. langsmith.Client, langsmith.wrappers.wrap_openai) see the
# values too. pydantic-settings only populates the Settings instance, not
# os.environ — that is not enough for SDKs that bypass our config object.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:
    pass


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    langsmith_api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="multi-agent-research-lab", validation_alias="LANGSMITH_PROJECT")

    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    google_model: str = Field(default="gemini-2.0-flash", validation_alias="GOOGLE_MODEL")

    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")
    brave_api_key: str | None = Field(default=None, validation_alias="BRAVE_API_KEY")

    max_iterations: int = Field(default=6, ge=1, le=20, validation_alias="MAX_ITERATIONS")
    timeout_seconds: int = Field(default=60, ge=5, le=600, validation_alias="TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
