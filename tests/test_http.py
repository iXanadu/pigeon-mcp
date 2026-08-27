"""Streamable HTTP transport — bearer auth and Hand tool allow-list."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from gmail_mcp.app import build_mcp
from gmail_mcp.config import settings


@pytest.fixture
def http_app():
    return build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )


async def test_http_without_bearer_returns_401(http_app):
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response.status_code == 401


async def test_http_401_advertises_mcp_resource_metadata(monkeypatch):
    """PRM must be path-scoped (/mcp); clients walk PRM → AS → authorize → /token."""
    monkeypatch.setattr(
        settings,
        "oauth_public_redirect_uri",
        "https://gmcp.example.com/oauth/callback",
    )
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
        well_known = await client.get("/.well-known/oauth-protected-resource/mcp")
        auth_server = await client.get("/.well-known/oauth-authorization-server")
        authorize = await client.get(
            "/authorize",
            params={
                "response_type": "code",
                "redirect_uri": "https://hand.example/cb",
                "state": "xyz",
            },
        )
        assert authorize.status_code == 302
        loc = authorize.headers["location"]
        assert "code=" in loc and "state=xyz" in loc
        from urllib.parse import parse_qs, urlsplit

        code = parse_qs(urlsplit(loc).query)["code"][0]
        token = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://hand.example/cb",
                "client_secret": settings.http_bearer_token,
            },
        )
        bare = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": "forged",
                "redirect_uri": "https://hand.example/cb",
            },
        )
        cc = await client.post(
            "/token",
            data={"grant_type": "client_credentials", "client_secret": settings.http_bearer_token},
        )
        reg = await client.post("/register", json={"redirect_uris": ["https://hand.example/cb"]})
    assert response.status_code == 401
    www = response.headers.get("www-authenticate", "")
    assert "/oauth-protected-resource/mcp" in www
    assert well_known.status_code == 200
    assert well_known.json()["resource"] == "https://gmcp.example.com/mcp"
    assert auth_server.status_code == 200
    meta = auth_server.json()
    assert meta["authorization_endpoint"].endswith("/authorize")
    assert "authorization_code" in meta["grant_types_supported"]
    assert token.status_code == 200
    assert token.json()["access_token"] == settings.http_bearer_token
    assert bare.status_code == 401
    assert cc.status_code == 200
    assert reg.status_code == 201
    assert reg.json()["client_secret"] == ""


async def test_oauth_callback_rejects_bad_state(http_app):
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/oauth/callback", params={"code": "x", "state": "nope"})
    assert response.status_code == 400


async def test_oauth_callback_completes(http_app, tmp_path, monkeypatch):
    from gmail_mcp.google_oauth import build_auth_url
    from gmail_mcp import accounts as accounts_mod
    import httpx
    import respx

    monkeypatch.setattr(settings, "tokens_dir", tmp_path / "tokens")
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    _, state = build_auth_url("https://gmcp.example/oauth/callback", client_id="cid", client_secret="sec")

    with respx.mock:
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "rt",
                    "expires_in": 3600,
                },
            )
        )
        respx.get("https://gmail.googleapis.com/gmail/v1/users/me/profile").mock(
            return_value=httpx.Response(200, json={"emailAddress": "hand@example.com"})
        )
        transport = ASGITransport(app=http_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/oauth/callback",
                params={"code": "auth-code", "state": state},
            )
    assert response.status_code == 200
    assert "hand@example.com" in response.text
    rows = await accounts_mod.accounts_list()
    assert any(r["account"] == "hand@example.com" for r in rows)
