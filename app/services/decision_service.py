from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision import Decision
from app.models.user import User


async def get_decisions_for_board(
    session: AsyncSession, board_id: int
) -> list[dict]:
    result = await session.execute(
        select(Decision, User.name)
        .outerjoin(User, Decision.author_id == User.id)
        .where(Decision.board_id == board_id)
        .order_by(Decision.created_at.asc())
    )
    rows = result.all()
    return [
        {
            "decision": row[0],
            "author_name": row[1],
        }
        for row in rows
    ]


async def get_decision(
    session: AsyncSession, decision_id: int, board_id: int
) -> dict | None:
    result = await session.execute(
        select(Decision, User.name)
        .outerjoin(User, Decision.author_id == User.id)
        .where(Decision.id == decision_id, Decision.board_id == board_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return {"decision": row[0], "author_name": row[1]}


async def update_decision(
    session: AsyncSession, decision_id: int, board_id: int, *, body: str
) -> dict:
    result = await session.execute(
        select(Decision).where(
            Decision.id == decision_id, Decision.board_id == board_id
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise ValueError("Decision not found")
    decision.body = body
    session.add(decision)
    await session.commit()
    await session.refresh(decision)
    result = await session.execute(
        select(Decision, User.name)
        .outerjoin(User, Decision.author_id == User.id)
        .where(Decision.id == decision.id)
    )
    row = result.one()
    return {"decision": row[0], "author_name": row[1]}


async def delete_decision(
    session: AsyncSession, decision_id: int, board_id: int
) -> None:
    result = await session.execute(
        select(Decision).where(
            Decision.id == decision_id, Decision.board_id == board_id
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise ValueError("Decision not found")
    await session.delete(decision)
    await session.commit()


async def create_decision(
    session: AsyncSession,
    *,
    board_id: int,
    body: str,
    author_id: int | None,
) -> dict:
    decision = Decision(
        board_id=board_id,
        body=body,
        author_id=author_id,
    )
    session.add(decision)
    await session.commit()
    await session.refresh(decision)
    result = await session.execute(
        select(Decision, User.name)
        .outerjoin(User, Decision.author_id == User.id)
        .where(Decision.id == decision.id)
    )
    row = result.one()
    return {
        "decision": row[0],
        "author_name": row[1],
    }
