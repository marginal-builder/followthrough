import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User
from app.services.feedback_service import create_feedback


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
async def alice_item(session: AsyncSession, board: int, alice: User):
    data = await create_feedback(
        session,
        board_id=board,
        column="start",
        body="Original body",
        author_id=alice.id,
    )
    return data["item"]


@pytest.fixture
async def bob_item(session: AsyncSession, board: int, bob: User):
    data = await create_feedback(
        session,
        board_id=board,
        column="stop",
        body="Bob item",
        author_id=bob.id,
    )
    return data["item"]


@pytest.fixture
async def anon_item(session: AsyncSession, board: int):
    data = await create_feedback(
        session,
        board_id=board,
        column="continue",
        body="Anonymous item",
        author_id=None,
    )
    return data["item"]


async def test_author_can_edit(alice_client: AsyncClient, board: int, alice_item):
    resp = await alice_client.get(f"/boards/{board}/feedback/{alice_item.id}")
    assert resp.status_code == 200
    assert "Original body" in resp.text
    assert "<textarea" in resp.text


async def test_author_save_edit(
    alice_client: AsyncClient, board: int, alice_item, session: AsyncSession
):
    resp = await alice_client.put(
        f"/boards/{board}/feedback/{alice_item.id}",
        data={"body": "Updated body"},
    )
    assert resp.status_code == 200
    assert "Updated body" in resp.text
    assert "Original body" not in resp.text


async def test_non_author_gets_403_on_edit(bob_client: AsyncClient, board: int, alice_item):
    resp = await bob_client.get(f"/boards/{board}/feedback/{alice_item.id}")
    assert resp.status_code == 403


async def test_non_author_gets_403_on_save(bob_client: AsyncClient, board: int, alice_item):
    resp = await bob_client.put(
        f"/boards/{board}/feedback/{alice_item.id}",
        data={"body": "Hacked"},
    )
    assert resp.status_code == 403


async def test_author_can_delete(
    alice_client: AsyncClient, board: int, alice_item, session: AsyncSession
):
    resp = await alice_client.delete(f"/boards/{board}/feedback/{alice_item.id}")
    assert resp.status_code == 200
    assert resp.text == ""


async def test_non_author_gets_403_on_delete(bob_client: AsyncClient, board: int, alice_item):
    resp = await bob_client.delete(f"/boards/{board}/feedback/{alice_item.id}")
    assert resp.status_code == 403


async def test_admin_can_edit_any_item(
    admin_client: AsyncClient, board: int, bob_item
):
    resp = await admin_client.get(f"/boards/{board}/feedback/{bob_item.id}")
    assert resp.status_code == 200
    assert "Bob item" in resp.text
    assert "<textarea" in resp.text


async def test_admin_can_delete_any_item(
    admin_client: AsyncClient, board: int, bob_item, session: AsyncSession
):
    resp = await admin_client.delete(f"/boards/{board}/feedback/{bob_item.id}")
    assert resp.status_code == 200


async def test_anonymous_item_editable_by_admin(
    admin_client: AsyncClient, board: int, anon_item
):
    resp = await admin_client.get(f"/boards/{board}/feedback/{anon_item.id}")
    assert resp.status_code == 200
    assert "Anonymous item" in resp.text


async def test_anonymous_item_not_editable_by_non_admin(
    bob_client: AsyncClient, board: int, anon_item
):
    resp = await bob_client.get(f"/boards/{board}/feedback/{anon_item.id}")
    assert resp.status_code == 403


async def test_edit_not_found(alice_client: AsyncClient, board: int):
    resp = await alice_client.get(f"/boards/{board}/feedback/99999")
    assert resp.status_code == 404


async def test_delete_not_found(alice_client: AsyncClient, board: int):
    resp = await alice_client.delete(f"/boards/{board}/feedback/99999")
    assert resp.status_code == 404


async def test_edit_wrong_board(
    alice_client: AsyncClient, board: int, alice_item, session: AsyncSession
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
    resp = await alice_client.get(f"/boards/{other_board}/feedback/{alice_item.id}")
    assert resp.status_code == 404
