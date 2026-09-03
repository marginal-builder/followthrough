from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_round_trip(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb\n"
        "VALKEY_URL=redis://localhost:6379/1\n"
        "TEAM_PASSCODE=testpass\n"
        "SESSION_SECRET=testsecret\n"
        "GROQ_API_KEY=gsk_test123\n"
    )

    settings = Settings(_env_file=str(env_file))

    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/testdb"
    assert settings.VALKEY_URL == "redis://localhost:6379/1"
    assert settings.TEAM_PASSCODE == "testpass"
    assert settings.SESSION_SECRET == "testsecret"
    assert settings.GROQ_API_KEY == "gsk_test123"


def test_settings_missing_database_url(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "VALKEY_URL=redis://localhost:6379/0\n"
        "TEAM_PASSCODE=changeme\n"
        "SESSION_SECRET=secret\n"
        "GROQ_API_KEY=key\n"
    )

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=str(env_file))

    assert "DATABASE_URL" in str(exc_info.value)


def test_settings_missing_session_secret(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://localhost:5432/test\n"
        "VALKEY_URL=redis://localhost:6379/0\n"
        "TEAM_PASSCODE=changeme\n"
        "GROQ_API_KEY=key\n"
    )

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=str(env_file))

    assert "SESSION_SECRET" in str(exc_info.value)
