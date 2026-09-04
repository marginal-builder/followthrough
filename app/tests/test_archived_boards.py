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


async def _insert_archived_board(session: AsyncSession, week_start: date, archived: bool) -> int:
    await session.execute(
        text(
            "INSERT INTO weekly_boards (week_start, is_archived) VALUES (:ws, :arch)"
        ),
        {"ws": week_start, "arch": archived},
    )
    await session.commit()
    result = await session.execute(
        text("SELECT id FROM weekly_boards WHERE week_start = :ws"), {"ws": week_start}
    )
    return result.scalar_one()


async def test_archived_board_shows_banner_and_hides_forms(
    logged_in_client: AsyncClient, session: AsyncSession
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    resp = await logged_in_client.get(f"/boards/{board_id}")
    assert resp.status_code == 200
    assert "This board is archived." in resp.text

    assert "Add feedback..." not in resp.text
    assert "Add action..." not in resp.text
    assert "Save Transcript" not in resp.text
    assert "Upload" not in resp.text
    assert "Approve" not in resp.text
    assert "Discard" not in resp.text


async def test_non_archived_board_no_banner(
    logged_in_client: AsyncClient, session: AsyncSession
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), False)

    resp = await logged_in_client.get(f"/boards/{board_id}")
    assert resp.status_code == 200
    assert "This board is archived." not in resp.text


async def test_archived_board_shows_existing_items(
    logged_in_client: AsyncClient, session: AsyncSession, seeded_user: User
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    await session.execute(
        text(
            "INSERT INTO feedback_items (board_id, \"column\", body, author_id, created_at) "
            "VALUES (:b, 'start', :body, :a, now())"
        ),
        {"b": board_id, "body": "Existing feedback item", "a": seeded_user.id},
    )
    await session.execute(
        text(
            "INSERT INTO actions (board_id, body, owner_id, status) "
            "VALUES (:b, :body, :a, 'todo')"
        ),
        {"b": board_id, "body": "Existing action item", "a": seeded_user.id},
    )
    await session.commit()

    resp = await logged_in_client.get(f"/boards/{board_id}")
    assert resp.status_code == 200
    assert "Existing feedback item" in resp.text
    assert "Existing action item" in resp.text


@pytest.mark.parametrize(
    "path,data",
    [
        ("/feedback", {"body": "test", "column": "start"}),
        ("/actions", {"body": "test", "owner_id": ""}),
        ("/decisions", {"body": "test"}),
    ],
)
async def test_post_to_archived_board_returns_403(
    logged_in_client: AsyncClient,
    session: AsyncSession,
    path: str,
    data: dict,
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    resp = await logged_in_client.post(f"/boards/{board_id}{path}", data=data)
    assert resp.status_code == 403


async def test_approve_discard_to_archived_board_returns_403(
    logged_in_client: AsyncClient, session: AsyncSession
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    await session.execute(
        text(
            "INSERT INTO extractions (board_id, kind, payload, status, created_at) "
            "VALUES (:b, 'action', '{}', 'pending', now())"
        ),
        {"b": board_id},
    )
    await session.commit()
    extraction_id = (
        await session.execute(text("SELECT id FROM extractions LIMIT 1"))
    ).scalar_one()

    resp_approve = await logged_in_client.post(
        f"/boards/{board_id}/extractions/{extraction_id}/approve"
    )
    assert resp_approve.status_code == 403

    resp_discard = await logged_in_client.post(
        f"/boards/{board_id}/extractions/{extraction_id}/discard"
    )
    assert resp_discard.status_code == 403


async def test_upload_to_archived_board_returns_403(
    logged_in_client: AsyncClient, session: AsyncSession
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    resp = await logged_in_client.post(
        f"/boards/{board_id}/upload",
        files={"file": ("audio.mp3", b"data", "audio/mpeg")},
    )
    assert resp.status_code == 403


async def test_paste_to_archived_board_returns_403(
    logged_in_client: AsyncClient, session: AsyncSession
):
    board_id = await _insert_archived_board(session, date(2026, 1, 5), True)

    resp = await logged_in_client.post(
        f"/boards/{board_id}/transcripts/paste", data={"text": "hello"}
    )
    assert resp.status_code == 403


async def test_create_board_archives_previous(
    logged_in_client: AsyncClient, session: AsyncSession
):
    first = await logged_in_client.post("/boards")
    assert first.status_code == 302
    first_id = int(first.headers["location"].rsplit("/", 1)[1])

    first_week = (
        await session.execute(
            text("SELECT week_start FROM weekly_boards WHERE id = :id"), {"id": first_id}
        )
    ).scalar_one()
    await session.execute(
        text("UPDATE weekly_boards SET week_start = :ws WHERE id = :id"),
        {"ws": date(2026, 1, 5), "id": first_id},
    )
    await session.commit()
    assert date(2026, 1, 5) != first_week

    second = await logged_in_client.post("/boards")
    assert second.status_code == 302
    second_id = int(second.headers["location"].rsplit("/", 1)[1])

    first_result = await session.execute(
        text("SELECT is_archived FROM weekly_boards WHERE id = :id"), {"id": first_id}
    )
    assert first_result.scalar_one() is True

    second_result = await session.execute(
        text("SELECT is_archived FROM weekly_boards WHERE id = :id"), {"id": second_id}
    )
    assert second_result.scalar_one() is False


async def test_create_board_same_week_is_noop_on_archives(
    logged_in_client: AsyncClient, session: AsyncSession
):
    first = await logged_in_client.post("/boards")
    assert first.status_code == 302
    first_id = int(first.headers["location"].rsplit("/", 1)[1])

    second = await logged_in_client.post("/boards")
    second_id = int(second.headers["location"].rsplit("/", 1)[1])

    assert first_id == second_id

    result = await session.execute(text("SELECT is_archived FROM weekly_boards"))
    flags = result.scalars().all()
    assert flags == [False]


async def test_boards_index_shows_archived_badge(
    logged_in_client: AsyncClient, session: AsyncSession
):
    await _insert_archived_board(session, date(2026, 1, 5), True)

    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    assert "Archived" in resp.text