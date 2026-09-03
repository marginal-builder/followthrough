import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User
from app.services.action_service import create_action


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
async def alice_action(session: AsyncSession, board: int, alice: User):
    data = await create_action(
        session,
        board_id=board,
        body="Fix the bug",
        owner_id=alice.id,
    )
    return data["action"]


async def test_create_action_with_owner(
    alice_client: AsyncClient, board: int, alice: User
):
    resp = await alice_client.post(
        f"/boards/{board}/actions",
        data={"body": "New action", "owner_id": str(alice.id)},
    )
    assert resp.status_code == 200
    assert "New action" in resp.text
    assert "Alice" in resp.text
    assert "To Do" in resp.text


async def test_status_transitions(
    alice_client: AsyncClient, board: int, alice_action
):
    resp = await alice_client.put(
        f"/boards/{board}/actions/{alice_action.id}",
        data={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert "In Progress" in resp.text

    resp = await alice_client.put(
        f"/boards/{board}/actions/{alice_action.id}",
        data={"status": "done"},
    )
    assert resp.status_code == 200
    assert "Done" in resp.text


async def test_action_without_due_date_renders_no_date_element(
    alice_client: AsyncClient, board: int, alice: User
):
    resp = await alice_client.post(
        f"/boards/{board}/actions",
        data={"body": "No due date action", "owner_id": str(alice.id)},
    )
    assert resp.status_code == 200
    assert "<time" not in resp.text


async def test_non_owner_cannot_change_status(
    bob_client: AsyncClient, board: int, alice_action
):
    resp = await bob_client.put(
        f"/boards/{board}/actions/{alice_action.id}",
        data={"status": "done"},
    )
    assert resp.status_code == 403


async def test_admin_can_change_any_status(
    admin_client: AsyncClient, board: int, alice_action
):
    resp = await admin_client.put(
        f"/boards/{board}/actions/{alice_action.id}",
        data={"status": "done"},
    )
    assert resp.status_code == 200
    assert "Done" in resp.text


async def test_empty_state(alice_client: AsyncClient, board: int):
    resp = await alice_client.get(f"/boards/{board}")
    assert resp.status_code == 200
    assert "No actions yet" in resp.text
