from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.user import User


async def get_actions_for_board(
    session: AsyncSession, board_id: int
) -> list[dict]:
    result = await session.execute(
        select(Action, User.name)
        .outerjoin(User, Action.owner_id == User.id)
        .where(Action.board_id == board_id)
        .order_by(Action.due_date.nullslast(), Action.id.asc())
    )
    rows = result.all()
    return [
        {
            "action": row[0],
            "owner_name": row[1],
        }
        for row in rows
    ]


async def create_action(
    session: AsyncSession,
    *,
    board_id: int,
    body: str,
    owner_id: int | None,
    due_date=None,
) -> dict:
    action = Action(
        board_id=board_id,
        body=body,
        owner_id=owner_id,
        due_date=due_date,
        status="todo",
    )
    session.add(action)
    await session.commit()
    await session.refresh(action)
    owner_id_val = action.owner_id
    result = await session.execute(
        select(Action, User.name)
        .outerjoin(User, Action.owner_id == User.id)
        .where(Action.id == action.id)
    )
    row = result.one()
    return {"action": row[0], "owner_name": row[1], "owner_id": owner_id_val}


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.name)
    )
    return list(result.scalars().all())


async def update_action_status(
    session: AsyncSession, action_id: int, board_id: int, status: str
) -> dict | None:
    if status not in ("todo", "in_progress", "done"):
        return None
    result = await session.execute(
        select(Action).where(
            Action.id == action_id, Action.board_id == board_id
        )
    )
    action = result.scalar_one_or_none()
    if action is None:
        return None
    action.status = status
    session.add(action)
    await session.commit()
    await session.refresh(action)
    owner_id_val = action.owner_id
    result = await session.execute(
        select(Action, User.name)
        .outerjoin(User, Action.owner_id == User.id)
        .where(Action.id == action.id)
    )
    row = result.one()
    return {"action": row[0], "owner_name": row[1], "owner_id": owner_id_val}
