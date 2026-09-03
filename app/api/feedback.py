from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services import feedback_service

router = APIRouter(prefix="/boards/{board_id}")

VALID_COLUMNS = {"start", "stop", "continue"}


@router.post("/feedback", response_class=HTMLResponse)
async def create_feedback(
    request: Request,
    board_id: int,
    body: str = Form(..., max_length=1000),
    column: str = Form(...),
    anonymous: str | None = Form(None),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    if column not in VALID_COLUMNS:
        return HTMLResponse(
            f"Invalid column: {column}", status_code=422
        )

    if not body.strip():
        return HTMLResponse("Body is required", status_code=422)

    author_id = None if anonymous == "on" else current_user.id

    data = await feedback_service.create_feedback(
        session,
        board_id=board_id,
        column=column,
        body=body.strip(),
        author_id=author_id,
    )

    return render(
        request,
        "boards/_feedback_item.html",
        {
            "item": data["item"],
            "author_name": data["author_name"],
        },
    )
