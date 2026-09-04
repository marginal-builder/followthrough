import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User
from app.models.transcript import Transcript


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


async def test_valid_paste_creates_transcript(
    logged_in_client: AsyncClient, session: AsyncSession, board: int
):
    resp = await logged_in_client.post(
        f"/boards/{board}/transcripts/paste",
        data={"text": "Meeting notes from standup"},
    )
    assert resp.status_code == 200
    assert "Transcript saved" in resp.text

    result = await session.exec(select(Transcript).where(Transcript.board_id == board))
    transcript = result.one()
    assert transcript.source == "paste"
    assert transcript.status == "ready"
    assert transcript.text == "Meeting notes from standup"


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
async def test_empty_paste_rejected(
    logged_in_client: AsyncClient, session: AsyncSession, board: int, text: str
):
    resp = await logged_in_client.post(
        f"/boards/{board}/transcripts/paste",
        data={"text": text},
    )
    assert resp.status_code == 400

    result = await session.exec(select(Transcript).where(Transcript.board_id == board))
    assert len(result.all()) == 0


async def test_unauthenticated_paste_redirects(client: AsyncClient, board: int, session: AsyncSession):
    resp = await client.post(
        f"/boards/{board}/transcripts/paste",
        data={"text": "Some text"},
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"

    result = await session.exec(select(Transcript).where(Transcript.board_id == board))
    assert len(result.all()) == 0
