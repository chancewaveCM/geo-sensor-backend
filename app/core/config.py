from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_KEY = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project
    PROJECT_NAME: str = "GEO Sensor API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8075
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = _INSECURE_SECRET_KEY

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """Block startup if using insecure default SECRET_KEY in non-debug mode."""
        if not self.DEBUG and self.SECRET_KEY == _INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY environment variable must be set in production. "
                "Set SECRET_KEY in .env file or environment variables."
            )
        return self

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./geo_sensor.db"

    # CORS - GEO Sensor uses port 3765 (frontend) / 8765 (backend)
    CORS_ORIGINS: list[str] = [
        "http://localhost:3765",  # GEO Sensor Frontend (primary)
        "http://localhost:3000",  # fallback for other envs
        "http://localhost:8765",  # GEO Sensor Backend
    ]

    # LLM Providers
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "gemini"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_MODEL: str = "gpt-5-nano"

    # Analysis Settings
    FUZZY_MATCH_THRESHOLD: float = 0.8
    SENTIMENT_CONFIDENCE_THRESHOLD: float = 0.7

    # Pipeline configuration
    PIPELINE_DEFAULT_CATEGORY_COUNT: int = 10
    PIPELINE_DEFAULT_QUERIES_PER_CATEGORY: int = 10
    PIPELINE_MAX_CONCURRENT_LLM_CALLS: int = 3
    PIPELINE_LLM_CALL_DELAY_MS: int = 200
    PIPELINE_LLM_TIMEOUT_SECONDS: int = 60
    PIPELINE_SCHEDULER_INTERVAL_SECONDS: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
