from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import unsign_user_id
from app.core.db import get_session
from app.models import User

templates = Jinja2Templates(directory="app/templates")


def get_current_user_id(request: Request) -> int | None:
    token = request.cookies.get("session")
    if token is None:
        return None
    return unsign_user_id(token)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    user_id = get_current_user_id(request)
    if user_id is None:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def render(
    request: Request,
    name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    ctx = context or {}
    ctx.setdefault("current_user", getattr(request.state, "current_user", None))
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
