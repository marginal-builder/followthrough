from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
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


@pytest.fixture
def mock_pool():
    job = Mock()
    job.job_id = "job-123"
    pool = AsyncMock()
    pool.enqueue_job.return_value = job
    app.state.redis_pool = pool
    yield pool
    app.state.redis_pool = None


async def test_unauthenticated_upload_redirects(client: AsyncClient, board: int):
    resp = await client.post(
        f"/boards/{board}/upload",
        files={"file": ("test.mp4", b"data", "video/mp4")},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_valid_upload_enqueues_job_and_returns_processing(
    logged_in_client: AsyncClient, mock_pool, board: int
):
    resp = await logged_in_client.post(
        f"/boards/{board}/upload",
        files={"file": ("recording.webm", b"some audio data", "audio/webm")},
    )
    assert resp.status_code == 200
    assert mock_pool.enqueue_job.call_count == 1
    args = mock_pool.enqueue_job.call_args.args
    assert args[0] == "transcribe_recording"
    assert args[1] == board
    assert isinstance(args[2], str)
    assert "Processing" in resp.text


async def test_empty_upload_returns_400(
    logged_in_client: AsyncClient, mock_pool, board: int
):
    resp = await logged_in_client.post(
        f"/boards/{board}/upload",
        files={"file": ("", b"", "audio/webm")},
    )
    assert resp.status_code == 400
    assert "No file uploaded" in resp.text


async def test_too_large_file_returns_400(
    logged_in_client: AsyncClient, mock_pool, board: int
):
    big = b"0" * (50 * 1024 * 1024 + 1)
    resp = await logged_in_client.post(
        f"/boards/{board}/upload",
        files={"file": ("large.mp4", big, "video/mp4")},
    )
    assert resp.status_code == 400
    assert "File too large" in resp.text
    mock_pool.enqueue_job.assert_not_called()


async def test_valid_upload_writes_file(logged_in_client: AsyncClient, mock_pool, board: int):
    from app.core.config import settings

    resp = await logged_in_client.post(
        f"/boards/{board}/upload",
        files={"file": ("clip.mp3", b"audio data", "audio/mpeg")},
    )
    assert resp.status_code == 200
    args = mock_pool.enqueue_job.call_args.args
    file_path = args[2]
    assert file_path.startswith(f"{settings.UPLOAD_DIR}/{board}/")
    assert file_path.endswith(".mp3")
