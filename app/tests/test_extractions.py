import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User
from app.models.extraction import Extraction


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)


@pytest.fixture
async def session(engine) -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def alice(session: AsyncSession) -> User:
    user = User(name="Alice")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def board(session: AsyncSession) -> int:
    from app.services.board_service import get_or_create_board

    b = await get_or_create_board(session)
    return b.id


@pytest.fixture
async def alice_client(client: AsyncClient, alice: User) -> AsyncClient:
    resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    client.cookies.update(resp.cookies)
    return client


@pytest.fixture
async def pending_action_extraction(session: AsyncSession, board: int) -> Extraction:
    ext = Extraction(
        board_id=board,
        kind="action",
        payload={"body": "Fix the bug", "owner_hint": "Alice", "due_date": "2025-07-01"},
        status="pending",
    )
    session.add(ext)
    await session.commit()
    await session.refresh(ext)
    return ext


@pytest.fixture
async def pending_decision_extraction(session: AsyncSession, board: int) -> Extraction:
    ext = Extraction(
        board_id=board,
        kind="decision",
        payload={"body": "Use Postgres"},
        status="pending",
    )
    session.add(ext)
    await session.commit()
    await session.refresh(ext)
    return ext


async def test_approve_action(
    alice_client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
    session: AsyncSession,
):
    resp = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/approve",
    )
    assert resp.status_code == 200
    assert "Fix the bug" in resp.text
    assert "Alice" in resp.text

    from sqlalchemy import select

    from app.models.action import Action

    result = await session.execute(
        select(Action).where(
            Action.board_id == board, Action.body == "Fix the bug"
        )
    )
    action = result.scalar_one()
    assert action.status == "todo"

    await session.refresh(pending_action_extraction)
    assert pending_action_extraction.status == "approved"


async def test_approve_decision(
    alice_client: AsyncClient,
    board: int,
    pending_decision_extraction: Extraction,
    session: AsyncSession,
):
    resp = await alice_client.post(
        f"/boards/{board}/extractions/{pending_decision_extraction.id}/approve",
    )
    assert resp.status_code == 200
    assert "Use Postgres" in resp.text

    from sqlalchemy import select

    from app.models.decision import Decision

    result = await session.execute(
        select(Decision).where(
            Decision.board_id == board, Decision.body == "Use Postgres"
        )
    )
    decision = result.scalar_one()
    assert decision.body == "Use Postgres"

    await session.refresh(pending_decision_extraction)
    assert pending_decision_extraction.status == "approved"


async def test_approve_action_resolves_owner(
    alice_client: AsyncClient,
    board: int,
    session: AsyncSession,
    alice: User,
):
    ext = Extraction(
        board_id=board,
        kind="action",
        payload={"body": "Task with owner", "owner_hint": "alice", "due_date": None},
        status="pending",
    )
    session.add(ext)
    await session.commit()
    await session.refresh(ext)

    resp = await alice_client.post(
        f"/boards/{board}/extractions/{ext.id}/approve",
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from app.models.action import Action

    result = await session.execute(
        select(Action).where(Action.body == "Task with owner")
    )
    action = result.scalar_one()
    assert action.owner_id == alice.id


async def test_approve_action_owner_hint_not_found(
    alice_client: AsyncClient,
    board: int,
    session: AsyncSession,
):
    ext = Extraction(
        board_id=board,
        kind="action",
        payload={"body": "Task no owner", "owner_hint": "nonexistent", "due_date": None},
        status="pending",
    )
    session.add(ext)
    await session.commit()
    await session.refresh(ext)

    resp = await alice_client.post(
        f"/boards/{board}/extractions/{ext.id}/approve",
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from app.models.action import Action

    result = await session.execute(
        select(Action).where(Action.body == "Task no owner")
    )
    action = result.scalar_one()
    assert action.owner_id is None


async def test_discard(
    alice_client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
    session: AsyncSession,
):
    resp = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/discard",
    )
    assert resp.status_code == 200
    assert resp.text == ""

    await session.refresh(pending_action_extraction)
    assert pending_action_extraction.status == "discarded"

    from sqlalchemy import select

    from app.models.action import Action

    result = await session.execute(
        select(Action).where(Action.body == "Fix the bug")
    )
    assert result.scalar_one_or_none() is None


async def test_approve_already_approved(
    alice_client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
    session: AsyncSession,
):
    resp1 = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/approve",
    )
    assert resp1.status_code == 200

    from sqlalchemy import select

    from app.models.action import Action

    result = await session.execute(select(Action).where(Action.body == "Fix the bug"))
    actions = list(result.scalars().all())
    assert len(actions) == 1

    resp2 = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/approve",
    )
    assert resp2.status_code == 200
    assert "Fix the bug" in resp2.text

    result2 = await session.execute(select(Action).where(Action.body == "Fix the bug"))
    actions2 = list(result2.scalars().all())
    assert len(actions2) == 1


async def test_approve_already_discarded(
    alice_client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
    session: AsyncSession,
):
    resp1 = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/discard",
    )
    assert resp1.status_code == 200

    resp2 = await alice_client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/approve",
    )
    assert resp2.status_code == 422


async def test_unauthenticated_approve(
    client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
):
    resp = await client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/approve",
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_unauthenticated_discard(
    client: AsyncClient,
    board: int,
    pending_action_extraction: Extraction,
):
    resp = await client.post(
        f"/boards/{board}/extractions/{pending_action_extraction.id}/discard",
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
