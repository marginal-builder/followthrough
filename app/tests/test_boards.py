import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User


@pytest.fixture
async def session(engine) -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)


@pytest.fixture
async def seeded_user(session: AsyncSession) -> User:
    user = User(name="Alice")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def logged_in_client(client: AsyncClient, seeded_user: User) -> AsyncClient:
    login_resp = await client.post(
        "/login",
        data={"user_id": str(seeded_user.id), "passcode": "changeme"},
    )
    client.cookies.update(login_resp.cookies)
    return client


async def test_unauthenticated_get_boards_redirects(client: AsyncClient):
    resp = await client.get("/boards")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_post_boards_creates_board(
    logged_in_client: AsyncClient, session: AsyncSession
):
    from sqlmodel import text

    resp = await logged_in_client.post("/boards")
    assert resp.status_code == 302
    assert "/boards/" in resp.headers["location"]

    result = await session.execute(text("SELECT count(*) FROM weekly_boards"))
    assert result.scalar_one() == 1


async def test_post_boards_twice_same_week_yields_same_board(
    logged_in_client: AsyncClient, session: AsyncSession
):
    from sqlmodel import text

    resp1 = await logged_in_client.post("/boards")
    resp2 = await logged_in_client.post("/boards")
    assert resp1.headers["location"] == resp2.headers["location"]

    result = await session.execute(text("SELECT count(*) FROM weekly_boards"))
    assert result.scalar_one() == 1


async def test_boards_newest_first(
    logged_in_client: AsyncClient, session: AsyncSession
):
    from datetime import date

    from sqlmodel import text

    # Insert two boards manually with different week_start dates
    older = date(2026, 1, 5)
    newer = date(2026, 1, 12)
    await session.execute(
        text(
            "INSERT INTO weekly_boards (week_start, is_archived) VALUES (:ws, false)"
        ),
        {"ws": older},
    )
    await session.execute(
        text(
            "INSERT INTO weekly_boards (week_start, is_archived) VALUES (:ws, false)"
        ),
        {"ws": newer},
    )
    await session.commit()

    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    text = resp.text
    pos_newer = text.index("2026-01-12")
    pos_older = text.index("2026-01-05")
    assert pos_newer < pos_older


async def test_empty_state_shown(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    assert "No boards yet" in resp.text


async def test_archived_badge_displayed(
    logged_in_client: AsyncClient, session: AsyncSession
):
    from datetime import date

    from sqlmodel import text

    await session.execute(
        text(
            "INSERT INTO weekly_boards (week_start, is_archived) VALUES (:ws, true)"
        ),
        {"ws": date(2026, 1, 5)},
    )
    await session.commit()

    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    assert "Archived" in resp.text


async def test_board_detail_page(
    logged_in_client: AsyncClient, session: AsyncSession
):
    resp = await logged_in_client.post("/boards")
    board_id = resp.headers["location"].split("/")[-1]

    detail_resp = await logged_in_client.get(f"/boards/{board_id}")
    assert detail_resp.status_code == 200
    assert f"Board {board_id}" in detail_resp.text


async def test_board_detail_nonexistent_redirects(
    logged_in_client: AsyncClient,
):
    resp = await logged_in_client.get("/boards/99999")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/boards"
