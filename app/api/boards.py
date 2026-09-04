from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services.action_service import get_actions_for_board, get_all_users
from app.services.board_service import get_board, get_boards, get_or_create_board
from app.services.decision_service import get_decisions_for_board
from app.services.extraction_service import get_pending_extractions
from app.services.feedback_service import get_items_for_board

router = APIRouter()


@router.get("/boards", response_class=HTMLResponse)
async def boards_list(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    request.state.current_user = current_user
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    boards = await get_boards(session)
    return render(
        request,
        "boards_list.html",
        {"current_user": current_user, "boards": boards},
    )


@router.post("/boards")
async def boards_create(
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    board = await get_or_create_board(session)
    return RedirectResponse(url=f"/boards/{board.id}", status_code=302)


@router.get("/boards/{board_id}", response_class=HTMLResponse)
async def boards_detail(
    request: Request,
    board_id: int,
    current_user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    request.state.current_user = current_user
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    board = await get_board(session, board_id)
    if board is None:
        return RedirectResponse(url="/boards", status_code=302)
    items = await get_items_for_board(session, board_id)
    items_by_column: dict[str, list[dict]] = defaultdict(list)
    for entry in items:
        items_by_column[entry["item"].column].append(entry)

    actions = await get_actions_for_board(session, board_id)
    decisions = await get_decisions_for_board(session, board_id)
    users = await get_all_users(session)
    pending_extractions = await get_pending_extractions(session, board_id)

    return render(
        request,
        "board_detail.html",
        {
            "current_user": current_user,
            "board": board,
            "items_by_column": items_by_column,
            "actions": actions,
            "decisions": decisions,
            "users": users,
            "pending_extractions": pending_extractions,
        },
    )
