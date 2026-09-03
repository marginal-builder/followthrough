from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User


@pytest.fixture
async def session(engine) -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as session:
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


@pytest.fixture
async def board(session: AsyncSession) -> int:
    from app.services.board_service import get_or_create_board

    b = await get_or_create_board(session)
    return b.id


async def test_unauthenticated_get_boards_redirects(client: AsyncClient):
    resp = await client.get("/boards")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_post_boards_creates_board(
    logged_in_client: AsyncClient, session: AsyncSession
):
    resp = await logged_in_client.post("/boards")
    assert resp.status_code == 302
    assert "/boards/" in resp.headers["location"]

    result = await session.execute(text("SELECT count(*) FROM weekly_boards"))
    assert result.scalar_one() == 1


async def test_post_boards_twice_same_week_yields_same_board(
    logged_in_client: AsyncClient, session: AsyncSession
):
    resp1 = await logged_in_client.post("/boards")
    resp2 = await logged_in_client.post("/boards")
    assert resp1.headers["location"] == resp2.headers["location"]

    result = await session.execute(text("SELECT count(*) FROM weekly_boards"))
    assert result.scalar_one() == 1


async def test_boards_newest_first(
    logged_in_client: AsyncClient, session: AsyncSession
):
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
    page_text = resp.text
    pos_newer = page_text.index("2026-01-12")
    pos_older = page_text.index("2026-01-05")
    assert pos_newer < pos_older


async def test_empty_state_shown(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    assert "No boards yet" in resp.text


async def test_archived_badge_displayed(
    logged_in_client: AsyncClient, session: AsyncSession
):
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
    logged_in_client: AsyncClient, board: int
):
    resp = await logged_in_client.get(f"/boards/{board}")
    assert resp.status_code == 200
    assert "Start" in resp.text
    assert "Stop" in resp.text
    assert "Continue" in resp.text


async def test_unauthenticated_board_detail_redirects(client: AsyncClient, board: int):
    resp = await client.get(f"/boards/{board}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_board_detail_nonexistent_redirects(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/boards/99999")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/boards"


async def test_empty_column_shows_no_items(
    logged_in_client: AsyncClient, board: int
):
    resp = await logged_in_client.get(f"/boards/{board}")
    assert resp.status_code == 200
    assert resp.text.count("No items yet") == 3


async def test_anonymous_item_shows_anonymous(
    logged_in_client: AsyncClient, board: int
):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "Great work", "column": "start", "anonymous": "on"},
    )
    assert resp.status_code == 200
    assert "Anonymous" in resp.text
    assert "Great work" in resp.text


async def test_authenticated_item_shows_name(
    logged_in_client: AsyncClient, seeded_user: User, board: int
):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "Good job", "column": "stop"},
    )
    assert resp.status_code == 200
    assert seeded_user.name in resp.text
    assert "Good job" in resp.text


async def test_create_feedback_non_anonymous(
    logged_in_client: AsyncClient, seeded_user: User, board: int, session: AsyncSession
):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "Keep it up", "column": "continue"},
    )
    assert resp.status_code == 200
    assert "Keep it up" in resp.text

    result = await session.execute(text("SELECT author_id FROM feedback_items"))
    author_id = result.scalar_one()
    assert author_id == seeded_user.id


async def test_create_feedback_anonymous(
    logged_in_client: AsyncClient, board: int, session: AsyncSession
):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "Needs improvement", "column": "stop", "anonymous": "on"},
    )
    assert resp.status_code == 200

    result = await session.execute(text("SELECT author_id FROM feedback_items"))
    author_id = result.scalar_one()
    assert author_id is None


async def test_create_feedback_invalid_column(logged_in_client: AsyncClient, board: int):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "Test", "column": "invalid"},
    )
    assert resp.status_code == 422


async def test_create_feedback_empty_body(logged_in_client: AsyncClient, board: int):
    resp = await logged_in_client.post(
        f"/boards/{board}/feedback",
        data={"body": "", "column": "start"},
    )
    assert resp.status_code == 422
