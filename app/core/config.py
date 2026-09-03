from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    VALKEY_URL: str
    TEAM_PASSCODE: str
    SESSION_SECRET: str
    GROQ_API_KEY: str

    UPLOAD_DIR: str = "/tmp/followthrough"
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()