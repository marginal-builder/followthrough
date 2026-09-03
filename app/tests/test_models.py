from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Action, Decision, Extraction, FeedbackItem, User, WeeklyBoard


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session


async def make_board(session: AsyncSession, week_start: date = date(2026, 9, 7)) -> WeeklyBoard:
    board = WeeklyBoard(week_start=week_start)
    session.add(board)
    await session.commit()
    await session.refresh(board)
    return board


async def test_create_user(session: AsyncSession) -> None:
    user = User(name="Alice")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.is_admin is False
    assert user.name == "Alice"


async def test_user_name_is_unique(session: AsyncSession) -> None:
    session.add(User(name="Bob"))
    await session.commit()

    session.add(User(name="Bob"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_weekly_board(session: AsyncSession) -> None:
    board = await make_board(session)

    assert board.id is not None
    assert board.is_archived is False


async def test_weekly_board_week_start_is_unique(session: AsyncSession) -> None:
    await make_board(session, date(2026, 9, 7))

    session.add(WeeklyBoard(week_start=date(2026, 9, 7)))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_feedback_item(session: AsyncSession) -> None:
    board = await make_board(session)

    item = FeedbackItem(board_id=board.id, column="start", body="Ship faster")
    session.add(item)
    await session.commit()
    await session.refresh(item)

    assert item.id is not None
    assert item.body == "Ship faster"
    assert item.created_at is not None


@pytest.mark.parametrize("column", ["start", "stop", "continue"])
async def test_feedback_item_valid_columns(session: AsyncSession, column: str) -> None:
    board = await make_board(session)

    item = FeedbackItem(board_id=board.id, column=column, body="Some feedback")
    session.add(item)
    await session.commit()
    await session.refresh(item)

    assert item.column == column


async def test_feedback_item_invalid_column_fails(session: AsyncSession) -> None:
    board = await make_board(session)

    item = FeedbackItem(board_id=board.id, column="bogus", body="Some feedback")
    session.add(item)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_action(session: AsyncSession) -> None:
    board = await make_board(session)

    action = Action(board_id=board.id, body="Do the thing")
    session.add(action)
    await session.commit()
    await session.refresh(action)

    assert action.id is not None
    assert action.status == "todo"
    assert action.due_date is None
    assert action.owner_id is None


@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
async def test_action_valid_statuses(session: AsyncSession, status: str) -> None:
    board = await make_board(session)

    action = Action(board_id=board.id, body="Do the thing", status=status)
    session.add(action)
    await session.commit()
    await session.refresh(action)

    assert action.status == status


async def test_action_invalid_status_fails(session: AsyncSession) -> None:
    board = await make_board(session)

    action = Action(board_id=board.id, body="Do the thing", status="bogus")
    session.add(action)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_decision(session: AsyncSession) -> None:
    board = await make_board(session)

    decision = Decision(board_id=board.id, body="We decided this")
    session.add(decision)
    await session.commit()
    await session.refresh(decision)

    assert decision.id is not None
    assert decision.body == "We decided this"


async def test_create_extraction(session: AsyncSession) -> None:
    board = await make_board(session)

    extraction = Extraction(
        board_id=board.id, kind="action", payload={"body": "Extracted action"}
    )
    session.add(extraction)
    await session.commit()
    await session.refresh(extraction)

    assert extraction.id is not None
    assert extraction.status == "pending"


@pytest.mark.parametrize("kind", ["action", "decision"])
async def test_extraction_valid_kinds(session: AsyncSession, kind: str) -> None:
    board = await make_board(session)

    extraction = Extraction(board_id=board.id, kind=kind, payload={"body": "x"})
    session.add(extraction)
    await session.commit()
    await session.refresh(extraction)

    assert extraction.kind == kind


async def test_extraction_invalid_kind_fails(session: AsyncSession) -> None:
    board = await make_board(session)

    extraction = Extraction(board_id=board.id, kind="bogus", payload={"body": "x"})
    session.add(extraction)
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_deleting_board_cascades_to_children(session: AsyncSession) -> None:
    board = await make_board(session)

    session.add(FeedbackItem(board_id=board.id, column="start", body="F1"))
    session.add(Action(board_id=board.id, body="A1"))
    session.add(Decision(board_id=board.id, body="D1"))
    session.add(Extraction(board_id=board.id, kind="action", payload={"body": "E1"}))
    await session.commit()

    async def count(table: str) -> int:
        result = await session.execute(text(f"SELECT count(*) FROM {table}"))
        return result.scalar_one()

    assert await count("feedback_items") == 1
    assert await count("actions") == 1
    assert await count("decisions") == 1
    assert await count("extractions") == 1

    await session.delete(board)
    await session.commit()

    assert await count("feedback_items") == 0
    assert await count("actions") == 0
    assert await count("decisions") == 0
    assert await count("extractions") == 0
