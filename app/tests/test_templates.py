import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.models import User


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)


@pytest.fixture
async def logged_in_client(client: AsyncClient, engine):
    async with AsyncSession(engine) as session:
        alice = User(name="Alice")
        session.add(alice)
        await session.commit()
        await session.refresh(alice)
    login_resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    client.cookies.update(login_resp.cookies)
    return client


async def test_boards_page_renders_base_layout(
    logged_in_client: AsyncClient,
):
    """Rendering a template that extends base.html returns 200 with the app name."""
    resp = await logged_in_client.get("/boards")
    assert resp.status_code == 200
    assert "FollowThrough" in resp.text
    assert "<main" in resp.text


async def test_base_layout_exposes_blocks():
    """The base layout defines the expected Jinja2 blocks."""
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    env = templates.env
    template = env.get_template("base.html")
    assert "content" in template.blocks
    assert "extra_head" in template.blocks
    assert "extra_scripts" in template.blocks
    assert "title" in template.blocks


async def test_unauthenticated_boards_redirects(client: AsyncClient):
    """Without a session, /boards redirects to /login (no header rendered)."""
    resp = await client.get("/boards")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
