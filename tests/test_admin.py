"""Owner dashboard is public HTML; APIs require a passkey session."""

from httpx import ASGITransport, AsyncClient

from pigeon_mcp.app import build_mcp
from pigeon_mcp.config import settings
from pigeon_mcp.tenants import get_store


def _app():
    return build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )


async def test_admin_home_is_public():
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/~/")
    assert response.status_code == 200
    assert "Pigeon" in response.text
    assert "passkey" in response.text.lower()


async def test_admin_api_requires_session():
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        me = await client.get("/~/api/me")
        tenants = await client.get("/~/api/tenants")
        mint = await client.post("/~/api/tenants", json={"name": "cursor"})
    assert me.status_code == 401
    assert tenants.status_code == 401
    assert mint.status_code == 401


async def test_bootstrap_state_and_setup_cookie():
    store = get_store()
    token = store.create_setup_token()
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get(f"/~/setup?t={token}")
        assert page.status_code == 200
        assert "pigeon_setup" in page.headers.get("set-cookie", "")
        state = await client.get("/~/api/bootstrap-state")
    assert state.status_code == 200
    body = state.json()
    assert body["needsSetup"] is True
    assert body["hasPasskey"] is False
