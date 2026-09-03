import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings

TABLES = (
    "feedback_items",
    "extractions",
    "decisions",
    "actions",
    "weekly_boards",
    "users",
)


@pytest.fixture
async def engine() -> AsyncEngine:
    """Create a fresh async engine bound to the current test's event loop."""
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db(engine: AsyncEngine) -> None:
    """Truncate all tables before each test to guarantee isolation."""
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
