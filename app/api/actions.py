from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.models.action import Action
from app.services import action_service
from app.services.board_service import require_active_board

router = APIRouter(prefix="/boards/{board_id}")

VALID_STATUSES = {"todo", "in_progress", "done"}


def _can_change_status(
    user_id: int | None, is_admin: bool, owner_id: int | None
) -> bool:
    if user_id is None:
        return False
    return is_admin or user_id == owner_id


@router.post("/actions", response_class=HTMLResponse)
async def create_action(
    request: Request,
    board_id: int,
    body: str = Form(..., max_length=1000),
    owner_id: str = Form(...),
    due_date: str = Form(None),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _board=Depends(require_active_board),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    if not body.strip():
        return HTMLResponse("Body is required", status_code=422)

    user_id = current_user.id
    is_admin = current_user.is_admin

    parsed_owner_id = int(owner_id) if owner_id else None
    parsed_due_date = date.fromisoformat(due_date) if due_date else None

    data = await action_service.create_action(
        session,
        board_id=board_id,
        body=body.strip(),
        owner_id=parsed_owner_id,
        due_date=parsed_due_date,
    )

    can_change = _can_change_status(user_id, is_admin, data["owner_id"])

    return render(
        request,
        "boards/_action_item.html",
        {
            "action": data["action"],
            "owner_name": data["owner_name"],
            "board_id": board_id,
            "can_change_status": can_change,
        },
    )


@router.put("/actions/{action_id}", response_class=HTMLResponse)
async def update_action_status(
    request: Request,
    board_id: int,
    action_id: int,
    status: str = Form(...),
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)

    if status not in VALID_STATUSES:
        return HTMLResponse("Invalid status", status_code=422)

    user_id = current_user.id
    is_admin = current_user.is_admin

    result = await session.execute(
        select(Action).where(
            Action.id == action_id, Action.board_id == board_id
        )
    )
    action = result.scalar_one_or_none()
    if action is None:
        return HTMLResponse("Not found", status_code=404)

    owner_id = action.owner_id
    if not _can_change_status(user_id, is_admin, owner_id):
        return HTMLResponse("Forbidden", status_code=403)

    data = await action_service.update_action_status(
        session, action_id, board_id, status
    )

    can_change = _can_change_status(user_id, is_admin, data["owner_id"])

    return render(
        request,
        "boards/_action_item.html",
        {
            "action": data["action"],
            "owner_name": data["owner_name"],
            "board_id": board_id,
            "can_change_status": can_change,
        },
    )
