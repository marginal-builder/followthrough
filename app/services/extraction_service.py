from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.decision import Decision
from app.models.extraction import Extraction
from app.models.user import User


async def get_pending_extractions(
    session: AsyncSession, board_id: int
) -> list[Extraction]:
    result = await session.execute(
        select(Extraction)
        .where(
            Extraction.board_id == board_id,
            Extraction.status == "pending",
        )
        .order_by(Extraction.created_at.asc())
    )
    return list(result.scalars().all())


async def _resolve_owner(
    session: AsyncSession, owner_hint: str | None
) -> int | None:
    if not owner_hint:
        return None
    result = await session.execute(
        select(User).where(User.name.ilike(owner_hint.strip()))
    )
    user = result.scalar_one_or_none()
    return user.id if user else None


def _parse_due_date(due_date_str: str | None) -> date | None:
    if not due_date_str:
        return None
    try:
        return date.fromisoformat(due_date_str)
    except ValueError:
        return None


async def approve_extraction(
    session: AsyncSession, extraction_id: int, board_id: int
) -> dict | None:
    result = await session.execute(
        select(Extraction).where(
            Extraction.id == extraction_id,
            Extraction.board_id == board_id,
        )
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        return None

    if extraction.status == "discarded":
        return {"error": "discarded"}

    if extraction.status == "approved":
        return await _get_existing_item(session, extraction)

    owner_id = None
    due_date = None

    if extraction.kind == "action":
        owner_id = await _resolve_owner(session, extraction.payload.get("owner_hint"))
        due_date = _parse_due_date(extraction.payload.get("due_date"))
        action = Action(
            board_id=board_id,
            body=extraction.payload["body"],
            owner_id=owner_id,
            due_date=due_date,
            status="todo",
        )
        session.add(action)
        extraction.status = "approved"
        await session.commit()
        await session.refresh(action)

        res = await session.execute(
            select(Action, User.name)
            .outerjoin(User, Action.owner_id == User.id)
            .where(Action.id == action.id)
        )
        row = res.one()
        return {
            "kind": "action",
            "action": row[0],
            "owner_name": row[1],
            "board_id": board_id,
        }
    else:
        decision = Decision(
            board_id=board_id,
            body=extraction.payload["body"],
        )
        session.add(decision)
        extraction.status = "approved"
        await session.commit()
        await session.refresh(decision)

        res = await session.execute(
            select(Decision, User.name)
            .outerjoin(User, Decision.author_id == User.id)
            .where(Decision.id == decision.id)
        )
        row = res.one()
        return {
            "kind": "decision",
            "decision": row[0],
            "author_name": row[1],
            "board_id": board_id,
        }


async def _get_existing_item(
    session: AsyncSession, extraction: Extraction
) -> dict | None:
    if extraction.kind == "action":
        result = await session.execute(
            select(Action, User.name)
            .outerjoin(User, Action.owner_id == User.id)
            .where(
                Action.board_id == extraction.board_id,
                Action.body == extraction.payload["body"],
            )
            .order_by(Action.id.desc())
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "kind": "action",
            "action": row[0],
            "owner_name": row[1],
            "board_id": extraction.board_id,
        }
    else:
        result = await session.execute(
            select(Decision, User.name)
            .outerjoin(User, Decision.author_id == User.id)
            .where(
                Decision.board_id == extraction.board_id,
                Decision.body == extraction.payload["body"],
            )
            .order_by(Decision.id.desc())
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "kind": "decision",
            "decision": row[0],
            "author_name": row[1],
            "board_id": extraction.board_id,
        }


async def discard_extraction(
    session: AsyncSession, extraction_id: int, board_id: int
) -> dict | None:
    result = await session.execute(
        select(Extraction).where(
            Extraction.id == extraction_id,
            Extraction.board_id == board_id,
        )
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        return None

    if extraction.status == "discarded":
        return {"already_discarded": True}

    extraction.status = "discarded"
    session.add(extraction)
    await session.commit()
    return {"ok": True}
