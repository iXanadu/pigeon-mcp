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


async def test_http_with_invalid_bearer_returns_401(http_app):
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    headers = {"Authorization": "Bearer wrong-token"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers=headers,
        )
    assert response.status_code == 401
