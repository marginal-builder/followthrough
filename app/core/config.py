from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/followthrough"

    # Valkey/Redis
    VALKEY_URL: str = "redis://localhost:6379/0"

    # Auth
    TEAM_PASSCODE: str = "changeme"
    SESSION_SECRET: str = "dev-secret-change-in-production"

    # Groq API
    GROQ_API_KEY: str = ""


settings = Settings()