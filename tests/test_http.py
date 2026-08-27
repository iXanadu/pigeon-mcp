"""Streamable HTTP transport — bearer auth and Hand tool allow-list."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from pigeon_mcp.app import build_mcp
from pigeon_mcp.config import settings


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


async def test_healthz_unauthenticated_200(http_app):
    """Watchdogs use curl -sf; /mcp 401 would false-restart a healthy process."""
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "ok"


async def test_http_401_omits_oauth_discovery(monkeypatch):
    """Public AS/PRM stays off — Hand must send the static Authorization bearer."""
    monkeypatch.setattr(
        settings,
        "oauth_public_redirect_uri",
        "https://pigeon.example.com/oauth/callback",
    )
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
        prm = await client.get("/.well-known/oauth-protected-resource")
        prm_mcp = await client.get("/.well-known/oauth-protected-resource/mcp")
        as_meta = await client.get("/.well-known/oauth-authorization-server")
        authorize = await client.get("/authorize")
    assert response.status_code == 401
    www = response.headers.get("www-authenticate", "")
    assert "resource_metadata=" not in www
    assert prm.status_code == 404
    assert prm_mcp.status_code == 404
    assert as_meta.status_code == 404
    assert authorize.status_code == 404


async def test_oauth_callback_rejects_bad_state(http_app):
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/oauth/callback", params={"code": "x", "state": "nope"})
    assert response.status_code == 400


async def test_oauth_callback_completes(http_app, tmp_path, monkeypatch):
    from pigeon_mcp.google_oauth import build_auth_url
    from pigeon_mcp import accounts as accounts_mod
    import httpx
    import respx

    monkeypatch.setattr(settings, "tokens_dir", tmp_path / "tokens")
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    _, state = build_auth_url("https://pigeon.example/oauth/callback", client_id="cid", client_secret="sec")

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


async def test_outbox_stage_requires_bearer(http_app, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "outbox_root", tmp_path / "Outbox")
    transport = ASGITransport(app=http_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outbox/stage",
            content=b"hello",
            headers={"x-filename": "hello.txt"},
        )
    assert response.status_code == 401


async def test_outbox_stage_writes_under_outbox(http_app, tmp_path, monkeypatch):
    outbox = tmp_path / "Outbox"
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "http_bearer_token", "stage-secret")
    # rebuild app so route closes over updated settings... settings is module singleton, ok
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outbox/stage?filename=deed.pdf",
            content=b"%PDF-fake",
            headers={"Authorization": "Bearer stage-secret"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "deed.pdf"
    assert body["size"] == 9
    path = Path(body["path"])
    assert path.is_file()
    assert path.read_bytes() == b"%PDF-fake"
    assert path.parent == outbox.resolve()


async def test_outbox_stage_rejects_oversize(http_app, tmp_path, monkeypatch):
    from pigeon_mcp.attachments import MAX_TOTAL_BYTES

    monkeypatch.setattr(settings, "outbox_root", tmp_path / "Outbox")
    monkeypatch.setattr(settings, "http_bearer_token", "stage-secret")
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outbox/stage?filename=big.bin",
            content=b"x" * (MAX_TOTAL_BYTES + 1),
            headers={"Authorization": "Bearer stage-secret"},
        )
    assert response.status_code == 413


async def test_outbox_stage_preserves_human_filename(http_app, tmp_path, monkeypatch):
    """Spaces/parens must survive — do not mangle 'Q3 Report.docx'."""
    outbox = tmp_path / "Outbox"
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "http_bearer_token", "stage-secret")
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outbox/stage",
            params={"filename": "Q3 Report (signed).docx"},
            content=b"doc-bytes",
            headers={"Authorization": "Bearer stage-secret"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "Q3 Report (signed).docx"
    assert (outbox / "Q3 Report (signed).docx").read_bytes() == b"doc-bytes"


def test_sanitize_rejects_encoded_dot_traversal_alone():
    """Standalone %2e case — no literal '..' to mask a broken check (admin lesson)."""
    from urllib.parse import unquote

    from pigeon_mcp.attachments import sanitize_outbox_filename

    raw = unquote("%2e%2e%2fevil.sh")
    with pytest.raises(ValueError):
        sanitize_outbox_filename(raw)
    with pytest.raises(ValueError):
        sanitize_outbox_filename("../evil.sh")


def test_sanitize_allows_percent_in_business_filenames():
    """Post-decode '%' is ordinary (100% complete.xlsx); edge blocks %2e/%2f pre-decode."""
    from pigeon_mcp.attachments import sanitize_outbox_filename

    assert sanitize_outbox_filename("100% complete.xlsx") == "100% complete.xlsx"
    assert sanitize_outbox_filename("Q3 margin 12% v2.docx") == "Q3 margin 12% v2.docx"


async def test_outbox_stage_double_encoded_becomes_literal_basename_with_bearer(
    http_app, tmp_path, monkeypatch
):
    """One URL decode → literal %2e… basename in outbox; not traversal (admin ruling)."""
    outbox = tmp_path / "Outbox"
    outbox.mkdir()
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "http_bearer_token", "stage-secret")
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.http_host,
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outbox/stage",
            params={"filename": "%252e%252e%252fevil"},
            content=b"x",
            headers={"Authorization": "Bearer stage-secret"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    staged = Path(body["path"])
    assert staged.read_bytes() == b"x"
    assert staged.parent.resolve() == outbox.resolve()
    assert not (tmp_path / "evil").exists()
