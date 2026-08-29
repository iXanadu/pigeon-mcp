"""Tests for send-as identities (identities_list + from_identity)."""

import base64
from email import message_from_bytes

import httpx
import pytest
import respx

from pigeon_mcp.config import settings
from pigeon_mcp.identities import list_identities, resolve_sender
from pigeon_mcp.idempotency import IdempotencyStore
from pigeon_mcp.mail import send
from pigeon_mcp.mime_builder import build_mime
from pigeon_mcp.oauth_constants import STATUS_ACTIVE
from pigeon_mcp.token_store import AccountToken, TokenStore

GMAIL = "https://gmail.googleapis.com/gmail/v1"
GMAIL_UP = "https://gmail.googleapis.com/upload/gmail/v1"

SEND_AS = {
    "sendAs": [
        {"sendAsEmail": "mail@example.com", "displayName": "Mailroom", "isPrimary": True, "isDefault": True},
        {
            "sendAsEmail": "engram@example.com",
            "displayName": "Engram",
            "verificationStatus": "accepted",
            "signature": "<p>— Engram</p>",
        },
        {"sendAsEmail": "pending@example.com", "displayName": "Pending", "verificationStatus": "pending"},
    ]
}


@pytest.fixture
def id_env(tmp_path, monkeypatch):
    outbox = tmp_path / "Outbox"
    outbox.mkdir()
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "tokens_dir", tokens)
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    monkeypatch.setattr(
        "pigeon_mcp.mail._idempotency_store",
        lambda: IdempotencyStore(tmp_path / "idempotency.json"),
    )
    TokenStore(tokens).save(
        AccountToken(
            email="mail@example.com",
            refresh_token="rt",
            access_token="tok",
            expires_at="2099-01-01T00:00:00+00:00",
            status=STATUS_ACTIVE,
        )
    )
    return {"outbox": outbox}


def test_build_mime_from_name_and_reply_to():
    mime = build_mime(
        from_email="engram@example.com",
        from_name="Engram",
        reply_to="engram@example.com",
        to=["x@example.com"],
        subject="Hi",
        body="hello",
    )
    msg = message_from_bytes(mime)
    assert msg["From"] == "Engram <engram@example.com>"
    assert msg["Reply-To"] == "engram@example.com"


def test_build_mime_default_has_no_reply_to():
    mime = build_mime(from_email="a@b.com", to=["c@d.com"], subject="Hi", body="x")
    msg = message_from_bytes(mime)
    assert msg["From"] == "a@b.com"
    assert msg["Reply-To"] is None


@respx.mock
async def test_identities_list_filters_unverified(id_env):
    respx.get(f"{GMAIL}/users/me/settings/sendAs").mock(return_value=httpx.Response(200, json=SEND_AS))
    result = await list_identities("mail@example.com")
    emails = [r["email"] for r in result["identities"]]
    assert emails == ["mail@example.com", "engram@example.com"]
    engram = result["identities"][1]
    assert engram["displayName"] == "Engram"
    assert engram["hasSignature"] is True
    assert result["identities"][0]["isPrimary"] is True


@respx.mock
async def test_resolve_sender_empty_keeps_account(id_env):
    respx.get(f"{GMAIL}/users/me/settings/sendAs/mail@example.com").mock(
        return_value=httpx.Response(200, json={"signature": "<p>sig</p>"})
    )
    sender = await resolve_sender("tok", "mail@example.com", "")
    assert sender.email == "mail@example.com"
    assert sender.display_name == ""
    assert sender.reply_to is None
    assert sender.signature_html == "<p>sig</p>"


@respx.mock
async def test_resolve_sender_rejects_unknown_and_pending(id_env):
    respx.get(f"{GMAIL}/users/me/settings/sendAs").mock(return_value=httpx.Response(200, json=SEND_AS))
    with pytest.raises(ValueError, match="not a verified send-as identity"):
        await resolve_sender("tok", "mail@example.com", "nobody@example.com")
    with pytest.raises(ValueError, match="pending@example.com"):
        await resolve_sender("tok", "mail@example.com", "pending@example.com")


@respx.mock
async def test_send_with_from_identity_sets_headers_and_signature(id_env):
    respx.get(f"{GMAIL}/users/me/settings/sendAs").mock(return_value=httpx.Response(200, json=SEND_AS))
    captured: dict = {}

    def _capture(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "m-1", "threadId": "t-1"})

    respx.post(f"{GMAIL_UP}/users/me/messages/send").mock(side_effect=_capture)

    proof_mime = build_mime(
        from_email="engram@example.com",
        from_name="Engram",
        reply_to="engram@example.com",
        to=["x@example.com"],
        subject="Hi",
        body="hello",
        signature_html="<p>— Engram</p>",
        signature_plain="— Engram",
    )
    raw_b64 = base64.urlsafe_b64encode(proof_mime).decode().rstrip("=")
    respx.get(f"{GMAIL}/users/me/messages/m-1").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "m-1",
                    "threadId": "t-1",
                    "sizeEstimate": 100,
                    "payload": {"headers": [{"name": "From", "value": "Engram <engram@example.com>"}]},
                },
            ),
            httpx.Response(200, json={"raw": raw_b64}),
        ]
    )

    result = await send(
        account="mail@example.com",
        to="x@example.com",
        subject="Hi",
        idempotency_key="k1",
        body="hello",
        from_identity="ENGRAM@example.com",  # case-insensitive match
    )
    assert result["ok"] is True
    body = captured["body"]
    assert b"From: Engram <engram@example.com>" in body
    assert b"Reply-To: engram@example.com" in body
    assert b"Engram" in body  # alias signature, not the mailbox's


@respx.mock
async def test_send_unknown_identity_never_uploads(id_env):
    respx.get(f"{GMAIL}/users/me/settings/sendAs").mock(return_value=httpx.Response(200, json=SEND_AS))
    route = respx.post(f"{GMAIL_UP}/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "never"})
    )
    with pytest.raises(ValueError, match="not a verified send-as identity"):
        await send(
            account="mail@example.com",
            to="x@example.com",
            subject="Hi",
            idempotency_key="k2",
            body="hello",
            from_identity="ghost@example.com",
        )
    assert route.call_count == 0
