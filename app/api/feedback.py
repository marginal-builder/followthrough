from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services import feedback_service

router = APIRouter(prefix="/boards/{board_id}")

VALID_COLUMNS = {"start", "stop", "continue"}


def _can_edit(user: User | None, item_author_id: int | None) -> bool:
    if user is None:
        return False
    return user.is_admin or user.id == item_author_id


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
    can_edit = _can_edit(current_user, author_id)

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
            "board_id": board_id,
            "can_edit": can_edit,
        },
    )


@router.get("/feedback/{item_id}", response_class=HTMLResponse)
async def get_edit_form(
    request: Request,
    board_id: int,
    item_id: int,
    cancel: int = 0,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await feedback_service.get_feedback_item(session, item_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["item"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    can_edit = True

    if cancel:
        return render(
            request,
            "boards/_feedback_item.html",
            {
                "item": data["item"],
                "author_name": data["author_name"],
                "board_id": board_id,
                "can_edit": can_edit,
            },
        )

    return render(
        request,
        "boards/_feedback_edit_form.html",
        {
            "item": data["item"],
            "board_id": board_id,
        },
    )


@router.put("/feedback/{item_id}", response_class=HTMLResponse)
async def save_edit(
    request: Request,
    board_id: int,
    item_id: int,
    body: str = Form(..., max_length=1000),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await feedback_service.get_feedback_item(session, item_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["item"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    if not body.strip():
        return HTMLResponse("Body is required", status_code=422)

    can_edit = _can_edit(current_user, data["item"].author_id)

    updated = await feedback_service.update_feedback(
        session, item_id, board_id, body=body.strip()
    )

    return render(
        request,
        "boards/_feedback_item.html",
        {
            "item": updated["item"],
            "author_name": updated["author_name"],
            "board_id": board_id,
            "can_edit": can_edit,
        },
    )


@router.delete("/feedback/{item_id}", response_class=HTMLResponse)
async def delete_item(
    request: Request,
    board_id: int,
    item_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await feedback_service.get_feedback_item(session, item_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["item"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    await feedback_service.delete_feedback(session, item_id, board_id)

    return HTMLResponse("")
