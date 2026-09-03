from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.templates import get_current_user, render
from app.models import User
from app.services.board_service import get_board, get_boards, get_or_create_board

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
    return render(
        request,
        "board_detail.html",
        {"current_user": current_user, "board": board},
    )
