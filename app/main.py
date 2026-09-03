from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import seed_users
from app.core.config import settings
from app.core.db import get_session
from app.models import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_users()
    yield


app = FastAPI(
    title="FollowThrough",
    description="Team feedback and retrospective tool",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


from app.api.auth import router as auth_router, get_current_user_id

app.include_router(auth_router)


@app.get("/boards", response_class=HTMLResponse)
async def boards(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user_id = get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return HTMLResponse(f"<html><body><h1>Boards</h1><p>Welcome, {user.name}</p></body></html>")
