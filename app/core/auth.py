from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlmodel import select

from app.core.config import settings
from app.core.db import async_session_factory
from app.models import User

serializer = URLSafeTimedSerializer(settings.SESSION_SECRET)

SESSION_COOKIE = "session"


def sign_user_id(user_id: int) -> str:
    return serializer.dumps(user_id)


def unsign_user_id(token: str) -> int | None:
    try:
        return serializer.loads(token, max_age=60 * 60 * 24 * 30)
    except BadSignature:
        return None


def verify_passcode(candidate: str, expected: str | None = None) -> bool:
    import hmac

    if expected is None:
        expected = settings.TEAM_PASSCODE
    return hmac.compare_digest(candidate, expected)


async def get_user_by_id(user_id: int) -> User | None:
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def seed_users() -> None:
    """Insert two default users if none exist (idempotent)."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        for name in ("Alice", "Bob"):
            session.add(User(name=name))
        await session.commit()
