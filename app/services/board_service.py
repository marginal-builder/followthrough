from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

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
