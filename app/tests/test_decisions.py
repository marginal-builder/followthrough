import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User
from app.services.decision_service import create_decision


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
async def bob(session: AsyncSession) -> User:
    user = User(name="Bob")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def admin_user(session: AsyncSession) -> User:
    user = User(name="Admin", is_admin=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def alice_client(client: AsyncClient, alice: User) -> AsyncClient:
    resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    client.cookies.update(resp.cookies)
    return client


@pytest.fixture
async def bob_client(client: AsyncClient, bob: User) -> AsyncClient:
    resp = await client.post(
        "/login",
        data={"user_id": str(bob.id), "passcode": "changeme"},
    )
    client.cookies.update(resp.cookies)
    return client


@pytest.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    resp = await client.post(
        "/login",
        data={"user_id": str(admin_user.id), "passcode": "changeme"},
    )
    client.cookies.update(resp.cookies)
    return client


@pytest.fixture
async def alice_decision(session: AsyncSession, board: int, alice: User):
    data = await create_decision(
        session,
        board_id=board,
        body="Original decision",
        author_id=alice.id,
    )
    return data["decision"]


@pytest.fixture
async def bob_decision(session: AsyncSession, board: int, bob: User):
    data = await create_decision(
        session,
        board_id=board,
        body="Bob decision",
        author_id=bob.id,
    )
    return data["decision"]


async def test_add_decision_and_see_in_list(
    alice_client: AsyncClient, board: int, alice: User
):
    resp = await alice_client.post(
        f"/boards/{board}/decisions",
        data={"body": "We will use Postgres"},
    )
    assert resp.status_code == 200
    assert "We will use Postgres" in resp.text
    assert "Alice" in resp.text


async def test_oldest_first_ordering(
    session: AsyncSession, alice_client: AsyncClient, board: int, alice: User
):
    await create_decision(
        session, board_id=board, body="Older decision", author_id=alice.id
    )
    await create_decision(
        session, board_id=board, body="Newer decision", author_id=alice.id
    )
    resp = await alice_client.get(f"/boards/{board}")
    assert resp.status_code == 200
    older_pos = resp.text.index("Older decision")
    newer_pos = resp.text.index("Newer decision")
    assert older_pos < newer_pos


async def test_author_can_edit_decision(
    alice_client: AsyncClient, board: int, alice_decision
):
    resp = await alice_client.get(f"/boards/{board}/decisions/{alice_decision.id}")
    assert resp.status_code == 200
    assert "Original decision" in resp.text
    assert "<textarea" in resp.text


async def test_author_save_edit(
    alice_client: AsyncClient, board: int, alice_decision, session: AsyncSession
):
    resp = await alice_client.put(
        f"/boards/{board}/decisions/{alice_decision.id}",
        data={"body": "Updated decision"},
    )
    assert resp.status_code == 200
    assert "Updated decision" in resp.text
    assert "Original decision" not in resp.text


async def test_non_author_gets_403_on_edit(
    bob_client: AsyncClient, board: int, alice_decision
):
    resp = await bob_client.get(f"/boards/{board}/decisions/{alice_decision.id}")
    assert resp.status_code == 403


async def test_non_author_gets_403_on_save(
    bob_client: AsyncClient, board: int, alice_decision
):
    resp = await bob_client.put(
        f"/boards/{board}/decisions/{alice_decision.id}",
        data={"body": "Hacked"},
    )
    assert resp.status_code == 403


async def test_non_author_gets_403_on_delete(
    bob_client: AsyncClient, board: int, alice_decision
):
    resp = await bob_client.delete(f"/boards/{board}/decisions/{alice_decision.id}")
    assert resp.status_code == 403


async def test_author_can_delete_decision(
    alice_client: AsyncClient, board: int, alice_decision, session: AsyncSession
):
    resp = await alice_client.delete(f"/boards/{board}/decisions/{alice_decision.id}")
    assert resp.status_code == 200
    assert resp.text == ""


async def test_admin_can_edit_any_decision(
    admin_client: AsyncClient, board: int, bob_decision
):
    resp = await admin_client.get(f"/boards/{board}/decisions/{bob_decision.id}")
    assert resp.status_code == 200
    assert "Bob decision" in resp.text
    assert "<textarea" in resp.text


async def test_admin_can_delete_any_decision(
    admin_client: AsyncClient, board: int, bob_decision, session: AsyncSession
):
    resp = await admin_client.delete(f"/boards/{board}/decisions/{bob_decision.id}")
    assert resp.status_code == 200


async def test_unauthenticated_cannot_create(client: AsyncClient, board: int):
    resp = await client.post(
        f"/boards/{board}/decisions",
        data={"body": "Should fail"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_empty_body_validation(alice_client: AsyncClient, board: int):
    resp = await alice_client.post(
        f"/boards/{board}/decisions",
        data={"body": "   "},
    )
    assert resp.status_code == 422
    assert "Body is required" in resp.text


async def test_body_too_long(alice_client: AsyncClient, board: int):
    resp = await alice_client.post(
        f"/boards/{board}/decisions",
        data={"body": "x" * 2001},
    )
    assert resp.status_code == 422


async def test_edit_not_found(alice_client: AsyncClient, board: int):
    resp = await alice_client.get(f"/boards/{board}/decisions/99999")
    assert resp.status_code == 404


async def test_delete_not_found(alice_client: AsyncClient, board: int):
    resp = await alice_client.delete(f"/boards/{board}/decisions/99999")
    assert resp.status_code == 404


async def test_edit_wrong_board(
    alice_client: AsyncClient, board: int, alice_decision, session: AsyncSession
):
    from datetime import date

    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO weekly_boards (week_start, is_archived) VALUES (:ws, false)"
        ),
        {"ws": date(2025, 1, 6)},
    )
    await session.commit()

    result = await session.execute(
        text("SELECT id FROM weekly_boards WHERE id != :board_id"),
        {"board_id": board},
    )
    other_board = result.scalar_one()
    resp = await alice_client.get(f"/boards/{other_board}/decisions/{alice_decision.id}")
    assert resp.status_code == 404


async def test_cancel_edit_reverts(
    alice_client: AsyncClient, board: int, alice_decision
):
    resp = await alice_client.get(
        f"/boards/{board}/decisions/{alice_decision.id}?cancel=1"
    )
    assert resp.status_code == 200
    assert "Original decision" in resp.text
    assert "<textarea" not in resp.text
