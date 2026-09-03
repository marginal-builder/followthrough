from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback_item import FeedbackItem
from app.models.user import User


async def get_items_for_board(
    session: AsyncSession, board_id: int
) -> list[dict]:
    result = await session.execute(
        select(FeedbackItem, User.name)
        .outerjoin(User, FeedbackItem.author_id == User.id)
        .where(FeedbackItem.board_id == board_id)
        .order_by(FeedbackItem.column, FeedbackItem.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "item": row[0],
            "author_name": row[1],
        }
        for row in rows
    ]


async def get_feedback_item(
    session: AsyncSession, item_id: int, board_id: int
) -> dict | None:
    result = await session.execute(
        select(FeedbackItem, User.name)
        .outerjoin(User, FeedbackItem.author_id == User.id)
        .where(FeedbackItem.id == item_id, FeedbackItem.board_id == board_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return {"item": row[0], "author_name": row[1]}


async def update_feedback(
    session: AsyncSession, item_id: int, board_id: int, *, body: str
) -> dict:
    result = await session.execute(
        select(FeedbackItem).where(
            FeedbackItem.id == item_id, FeedbackItem.board_id == board_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError("Feedback item not found")
    item.body = body
    session.add(item)
    await session.commit()
    await session.refresh(item)
    result = await session.execute(
        select(FeedbackItem, User.name)
        .outerjoin(User, FeedbackItem.author_id == User.id)
        .where(FeedbackItem.id == item.id)
    )
    row = result.one()
    return {"item": row[0], "author_name": row[1]}


async def delete_feedback(
    session: AsyncSession, item_id: int, board_id: int
) -> None:
    result = await session.execute(
        select(FeedbackItem).where(
            FeedbackItem.id == item_id, FeedbackItem.board_id == board_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError("Feedback item not found")
    await session.delete(item)
    await session.commit()


async def create_feedback(
    session: AsyncSession,
    *,
    board_id: int,
    column: str,
    body: str,
    author_id: int | None,
) -> dict:
    item = FeedbackItem(
        board_id=board_id,
        column=column,
        body=body,
        author_id=author_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    result = await session.execute(
        select(FeedbackItem, User.name)
        .outerjoin(User, FeedbackItem.author_id == User.id)
        .where(FeedbackItem.id == item.id)
    )
    row = result.one()
    return {
        "item": row[0],
        "author_name": row[1],
    }
