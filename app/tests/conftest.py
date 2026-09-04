import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import settings

TABLES = (
    "transcripts",
    "feedback_items",
    "extractions",
    "decisions",
    "actions",
    "weekly_boards",
    "users",
)


@pytest.fixture
async def engine() -> AsyncEngine:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))


@pytest.fixture(autouse=True)
def override_session(engine: AsyncEngine):
    from app.main import app
    from app.core.db import get_session

    async def _override():
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    yield
    app.dependency_overrides.clear()
