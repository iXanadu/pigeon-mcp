"""Remote seats fetch pulled attachments: bearer + single-use ticket, tenant-scoped."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from pigeon_mcp.app import build_mcp
from pigeon_mcp.config import settings
from pigeon_mcp.inbox import get_attachment_file
from pigeon_mcp.oauth_constants import STATUS_ACTIVE
from pigeon_mcp.tenants import get_store, set_current_tenant
from pigeon_mcp.token_store import AccountToken, TokenStore

GMAIL = "https://gmail.googleapis.com/gmail/v1"
BOX = "agent@example.com"
OTHER_BOX = "owner@example.com"
DATA = b"%PDF-exhibit-a"


@pytest.fixture
def env(tmp_path, monkeypatch):
    downloads = tmp_path / "Inbox"
    downloads.mkdir()
    monkeypatch.setattr(settings, "download_root", downloads)
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    monkeypatch.setattr(settings, "http_public_url", "https://pigeon.example.com")
    tokens = TokenStore(settings.tokens_dir)
    for email in (BOX, OTHER_BOX):
        tokens.save(
            AccountToken(
                email=email,
                refresh_token="rt",
                access_token="tok",
                expires_at="2099-01-01T00:00:00+00:00",
                status=STATUS_ACTIVE,
            )
        )
    store = get_store()
    alice_id, alice = store.create_tenant("alice")
    store.grant(alice_id, BOX)
    bob_id, bob = store.create_tenant("bob")
    store.grant(bob_id, BOX)
    app = build_mcp(http=True).streamable_http_app(
        streamable_http_path="/mcp", host=settings.http_host
    )
    yield {
        "downloads": downloads,
        "store": store,
        "alice_id": alice_id,
        "alice": alice,
        "bob_id": bob_id,
        "bob": bob,
        "app": app,
    }
    set_current_tenant(None)


def _mock_gmail():
    respx.get(f"{GMAIL}/users/me/messages/m1/attachments/a1").mock(
        return_value=httpx.Response(
            200, json={"data": base64.urlsafe_b64encode(DATA).decode().rstrip("=")}
        )
    )


async def _pull_as(env, secret: str, output_path: str = "exhibit.pdf") -> dict:
    set_current_tenant(env["store"].resolve_bearer(secret))
    try:
        return await get_attachment_file(BOX, "m1", "a1", output_path)
    finally:
        set_current_tenant(None)


async def _get(env, url: str, secret: str | None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    transport = ASGITransport(app=env["app"], raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(url.replace("https://pigeon.example.com", ""), headers=headers)


@respx.mock
async def test_http_pull_lands_in_tenant_folder_with_link(env):
    _mock_gmail()
    result = await _pull_as(env, env["alice"])
    path = Path(result["path"])
    assert path.parent == (env["downloads"] / env["alice_id"]).resolve()
    assert result["sha256"] == hashlib.sha256(DATA).hexdigest()
    assert result["download_url"].startswith("https://pigeon.example.com/inbox/fetch/pgd_")


@respx.mock
async def test_http_pull_cannot_write_into_another_tenants_folder(env):
    _mock_gmail()
    target = env["downloads"] / env["bob_id"] / "planted.pdf"
    with pytest.raises(ValueError, match="under download root"):
        await _pull_as(env, env["alice"], str(target))
    with pytest.raises(ValueError, match="under download root"):
        await _pull_as(env, env["alice"], f"../{env['bob_id']}/planted.pdf")


@respx.mock
async def test_stdio_pull_has_no_link(env):
    _mock_gmail()
    result = await get_attachment_file(BOX, "m1", "a1", "plain.pdf")
    assert Path(result["path"]).parent == env["downloads"].resolve()
    assert "download_url" not in result


@respx.mock
async def test_fetch_serves_bytes_once(env):
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    resp = await _get(env, url, env["alice"])
    assert resp.status_code == 200
    assert resp.content == DATA
    assert resp.headers["content-type"] == "application/octet-stream"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"
    again = await _get(env, url, env["alice"])
    assert again.status_code == 404
    audit = env["store"].list_audit()
    assert any(a["tool"] == "inbox_fetch" and a["tenant_name"] == "alice" for a in audit)


@respx.mock
async def test_fetch_requires_bearer(env):
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    assert (await _get(env, url, None)).status_code == 401
    assert (await _get(env, url, "pgn_not-a-real-token")).status_code == 401
    # Failed auth must not burn the ticket.
    assert (await _get(env, url, env["alice"])).status_code == 200


@respx.mock
async def test_other_tenant_cannot_use_ticket_and_does_not_burn_it(env):
    """Bob shares the mailbox grant, but Alice's pull is still Alice's."""
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    assert (await _get(env, url, env["bob"])).status_code == 404
    assert (await _get(env, url, env["alice"])).status_code == 200


@respx.mock
async def test_revoked_grant_blocks_fetch(env):
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    env["store"].revoke_grant(env["alice_id"], BOX)
    assert (await _get(env, url, env["alice"])).status_code == 404


@respx.mock
async def test_rotated_bearer_kills_outstanding_tickets(env):
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    new_secret = env["store"].rotate_secret(env["alice_id"])
    assert (await _get(env, url, new_secret)).status_code == 404


@respx.mock
async def test_swapped_file_is_refused(env):
    _mock_gmail()
    result = await _pull_as(env, env["alice"])
    Path(result["path"]).write_bytes(b"%PDF-evil-tampered")
    assert (await _get(env, result["download_url"], env["alice"])).status_code == 404


@respx.mock
async def test_symlinked_file_is_refused(env):
    _mock_gmail()
    result = await _pull_as(env, env["alice"])
    path = Path(result["path"])
    outside = env["downloads"].parent / "secret.bin"
    outside.write_bytes(DATA)
    path.unlink()
    path.symlink_to(outside)
    assert (await _get(env, result["download_url"], env["alice"])).status_code == 404


@respx.mock
async def test_expired_ticket_is_refused(env):
    _mock_gmail()
    url = (await _pull_as(env, env["alice"]))["download_url"]
    env["store"]._exec("UPDATE download_ticket SET expires_at = '2000-01-01T00:00:00Z'")
    assert (await _get(env, url, env["alice"])).status_code == 404


async def test_ticket_hash_only_at_rest(env):
    secret, _ = env["store"].issue_download(
        tenant_id=env["alice_id"], account=BOX, path="/x", sha256="0" * 64, size=1
    )
    rows = env["store"]._fetchall("SELECT token_hash FROM download_ticket")
    assert all(secret.encode() not in bytes(r["token_hash"]) for r in rows)
