from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import SESSION_COOKIE, sign_user_id, unsign_user_id, verify_passcode
from app.core.db import get_session
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_current_user_id(request: Request) -> int | None:
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        return None
    return unsign_user_id(token)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _error: str | None = None,
):
    user_id = get_current_user_id(request)
    if user_id is not None:
        user = await session.get(User, user_id)
        if user is not None:
            return RedirectResponse(url="/boards", status_code=302)

    result = await session.execute(select(User).order_by(User.name))
    users = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"users": users, "error": _error},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    user_id: int = Form(...),
    passcode: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    if not passcode:
        return await _show_login_error(request, session, "Please enter a passcode")
    if user_id == 0:
        return await _show_login_error(request, session, "Please select a name")

    user = await session.get(User, user_id)
    if user is None:
        return await _show_login_error(request, session, "Please select a valid name")

    if not verify_passcode(passcode):
        return await _show_login_error(request, session, "Invalid passcode")

    token = sign_user_id(user.id)
    response = RedirectResponse(url="/boards", status_code=302)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


async def _show_login_error(
    request: Request, session: AsyncSession, error: str
) -> HTMLResponse:
    result = await session.execute(select(User).order_by(User.name))
    users = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"users": users, "error": error},
        status_code=200,
    )


@router.post("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
