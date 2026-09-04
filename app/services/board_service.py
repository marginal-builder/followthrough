from datetime import UTC, date, datetime, timedelta

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.models.weekly_board import WeeklyBoard


async def get_boards(session: AsyncSession) -> list[WeeklyBoard]:
    result = await session.execute(
        select(WeeklyBoard).order_by(WeeklyBoard.week_start.desc())
    )
    return list(result.scalars().all())


async def get_board(session: AsyncSession, board_id: int) -> WeeklyBoard | None:
    return await session.get(WeeklyBoard, board_id)


def current_week_monday() -> date:
    today = datetime.now(tz=UTC).date()
    return today - timedelta(days=today.weekday())


async def get_or_create_board(session: AsyncSession) -> WeeklyBoard:
    monday = current_week_monday()
    result = await session.execute(
        select(WeeklyBoard).where(WeeklyBoard.week_start == monday)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    board = WeeklyBoard(week_start=monday)
    session.add(board)
    try:
        await session.commit()
        await session.refresh(board)
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(WeeklyBoard).where(WeeklyBoard.week_start == monday)
        )
        return result.scalar_one()
    return board


async def archive_previous_unarchived(
    session: AsyncSession, exclude_board_id: int
) -> None:
    result = await session.execute(
        select(WeeklyBoard)
        .where(WeeklyBoard.is_archived == False, WeeklyBoard.id != exclude_board_id)
        .order_by(WeeklyBoard.week_start.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()
    if previous is not None:
        previous.is_archived = True
        session.add(previous)


async def require_active_board(
    board_id: int, session: AsyncSession = Depends(get_session)
) -> WeeklyBoard:
    board = await session.get(WeeklyBoard, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.is_archived:
        raise HTTPException(status_code=403, detail="Board is archived")
    return board
