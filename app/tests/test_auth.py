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
async def seeded_users(session: AsyncSession) -> list[User]:
    """Insert two users for auth tests."""
    alice = User(name="Alice")
    bob = User(name="Bob")
    session.add_all([alice, bob])
    await session.commit()
    await session.refresh(alice)
    await session.refresh(bob)
    return [alice, bob]


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)


async def test_happy_path_login_protected_logout(
    client: AsyncClient, seeded_users: list[User]
):
    """Login → access protected page → logout → access denied."""
    alice = seeded_users[0]

    # Login
    login_resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    assert login_resp.status_code == 302
    assert login_resp.headers["location"] == "/boards"
    assert "session" in login_resp.cookies

    # Access protected page with session cookie
    boards_resp = await client.get(
        "/boards", cookies=login_resp.cookies
    )
    assert boards_resp.status_code == 200
    assert "Alice" in boards_resp.text

    # Logout
    logout_resp = await client.post(
        "/logout", cookies=login_resp.cookies
    )
    assert logout_resp.status_code == 302
    assert logout_resp.headers["location"] == "/login"

    # After logout, accessing protected page should redirect
    after_logout = await client.get(
        "/boards", cookies=logout_resp.cookies
    )
    assert after_logout.status_code == 302
    assert after_logout.headers["location"] == "/login"


async def test_wrong_passcode_shows_error(
    client: AsyncClient, seeded_users: list[User]
):
    """Wrong passcode shows error and does not set a session cookie."""
    alice = seeded_users[0]
    resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "wrongpass"},
    )
    assert resp.status_code == 200
    assert "Invalid passcode" in resp.text
    assert "session" not in resp.cookies


async def test_no_passcode_shows_error(
    client: AsyncClient, seeded_users: list[User]
):
    """Submitting with no passcode stays on login with error."""
    alice = seeded_users[0]
    resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": ""},
    )
    assert resp.status_code == 200
    assert "Please enter a passcode" in resp.text


async def test_no_name_selected_shows_error(
    client: AsyncClient, seeded_users: list[User]
):
    """Submitting with no name selected stays on login with error."""
    resp = await client.post(
        "/login",
        data={"user_id": "0", "passcode": "changeme"},
    )
    assert resp.status_code == 200
    assert "Please select a name" in resp.text


async def test_protected_route_redirects_without_cookie(client: AsyncClient):
    """Accessing protected route without cookie redirects to /login (302)."""
    resp = await client.get("/boards")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


async def test_logout_clears_cookie_and_redirects(
    client: AsyncClient, seeded_users: list[User]
):
    """POST /logout clears the session cookie and redirects to /login."""
    alice = seeded_users[0]
    login_resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    logout_resp = await client.post(
        "/logout", cookies=login_resp.cookies
    )
    assert logout_resp.status_code == 302
    assert logout_resp.headers["location"] == "/login"
    # The cookie should be set to empty/expired
    set_cookie_header = logout_resp.headers.get("set-cookie", "")
    assert "session=" in set_cookie_header


async def test_login_page_lists_users(
    client: AsyncClient, seeded_users: list[User]
):
    """GET /login shows a page with user names in the dropdown."""
    resp = await client.get("/login")
    assert resp.status_code == 200
    assert "Alice" in resp.text
    assert "Bob" in resp.text
    assert "passcode" in resp.text


async def test_already_logged_in_redirects_to_boards(
    client: AsyncClient, seeded_users: list[User]
):
    """Visiting /login while already logged in redirects to /boards."""
    alice = seeded_users[0]
    login_resp = await client.post(
        "/login",
        data={"user_id": str(alice.id), "passcode": "changeme"},
    )
    resp = await client.get("/login", cookies=login_resp.cookies)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/boards"
