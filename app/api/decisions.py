from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services import decision_service

router = APIRouter(prefix="/boards/{board_id}")

MAX_BODY_LENGTH = 2000


def _can_edit(user: User | None, decision_author_id: int | None) -> bool:
    if user is None:
        return False
    return user.is_admin or user.id == decision_author_id


@router.post("/decisions", response_class=HTMLResponse)
async def create_decision(
    request: Request,
    board_id: int,
    body: str = Form(..., max_length=MAX_BODY_LENGTH),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    if not body.strip():
        return HTMLResponse("Body is required", status_code=422)

    data = await decision_service.create_decision(
        session,
        board_id=board_id,
        body=body.strip(),
        author_id=current_user.id,
    )

    return render(
        request,
        "boards/_decision_item.html",
        {
            "decision": data["decision"],
            "author_name": data["author_name"],
            "board_id": board_id,
            "can_edit": True,
        },
    )


@router.get("/decisions/{decision_id}", response_class=HTMLResponse)
async def get_edit_form(
    request: Request,
    board_id: int,
    decision_id: int,
    cancel: int = 0,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await decision_service.get_decision(session, decision_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["decision"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    can_edit = True

    if cancel:
        return render(
            request,
            "boards/_decision_item.html",
            {
                "decision": data["decision"],
                "author_name": data["author_name"],
                "board_id": board_id,
                "can_edit": can_edit,
            },
        )

    return render(
        request,
        "boards/_decision_edit_form.html",
        {
            "decision": data["decision"],
            "board_id": board_id,
        },
    )


@router.put("/decisions/{decision_id}", response_class=HTMLResponse)
async def save_edit(
    request: Request,
    board_id: int,
    decision_id: int,
    body: str = Form(..., max_length=MAX_BODY_LENGTH),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await decision_service.get_decision(session, decision_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["decision"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    if not body.strip():
        return HTMLResponse("Body is required", status_code=422)

    can_edit = _can_edit(current_user, data["decision"].author_id)

    updated = await decision_service.update_decision(
        session, decision_id, board_id, body=body.strip()
    )

    return render(
        request,
        "boards/_decision_item.html",
        {
            "decision": updated["decision"],
            "author_name": updated["author_name"],
            "board_id": board_id,
            "can_edit": can_edit,
        },
    )


@router.delete("/decisions/{decision_id}", response_class=HTMLResponse)
async def delete_decision(
    request: Request,
    board_id: int,
    decision_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    data = await decision_service.get_decision(session, decision_id, board_id)
    if data is None:
        return HTMLResponse("Not found", status_code=404)

    if not _can_edit(current_user, data["decision"].author_id):
        return HTMLResponse("Forbidden", status_code=403)

    await decision_service.delete_decision(session, decision_id, board_id)

    return HTMLResponse("")
