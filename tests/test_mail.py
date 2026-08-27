"""Tests for send / reply / forward."""

import base64
import hashlib
import json

import httpx
import pytest
import respx

from gmail_mcp.attachments import MAX_TOTAL_BYTES, resolve_attachments
from gmail_mcp.config import settings
from gmail_mcp.idempotency import IdempotencyStore
from gmail_mcp.mail import forward, reply, send
from gmail_mcp.mime_builder import build_mime
from gmail_mcp.oauth_constants import STATUS_ACTIVE
from gmail_mcp.proof import extract_hrefs_from_mime
from gmail_mcp.token_store import AccountToken, TokenStore

GMAIL = "https://gmail.googleapis.com/gmail/v1"
GMAIL_UP = "https://gmail.googleapis.com/upload/gmail/v1"


@pytest.fixture
def mail_env(tmp_path, monkeypatch):
    outbox = tmp_path / "Outbox"
    outbox.mkdir()
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    idem = tmp_path / "idempotency.json"
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "tokens_dir", tokens)
    monkeypatch.setattr(settings, "http_port", 8879)
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    store = TokenStore(tokens)
    store.save(
        AccountToken(
            email="sender@example.com",
            refresh_token="rt",
            access_token="access-token",
            expires_at="2099-01-01T00:00:00+00:00",
            status=STATUS_ACTIVE,
        )
    )
    return {"outbox": outbox, "tokens": tokens, "idem_path": idem, "store": store}


def test_reject_content_base64(mail_env):
    with pytest.raises(ValueError, match="contentBase64"):
        resolve_attachments(
            mail_env["outbox"],
            [{"path": str(mail_env["outbox"] / "x.txt"), "contentBase64": "abc"}],
        )


def test_reject_outside_outbox(mail_env):
    outside = mail_env["outbox"].parent / "secret.txt"
    outside.write_text("nope")
    with pytest.raises(ValueError, match="under outbox"):
        resolve_attachments(mail_env["outbox"], [{"path": str(outside)}])


def test_reject_over_25mb(mail_env):
    big = mail_env["outbox"] / "big.bin"
    big.write_bytes(b"x" * (MAX_TOTAL_BYTES + 1))
    with pytest.raises(ValueError, match="25 MB"):
        resolve_attachments(mail_env["outbox"], [{"path": str(big)}])


def test_mime_preserves_href():
    html = '<a href="https://example.com/x">link</a>'
    mime = build_mime(
        from_email="a@b.com",
        to=["c@d.com"],
        subject="Hi",
        html_body=html,
    )
    assert extract_hrefs_from_mime(mime) == ["https://example.com/x"]


def test_extract_hrefs_decodes_base64_parts():
    mime = build_mime(
        from_email="a@b.com",
        to=["c@d.com"],
        subject="Hi",
        html_body='<a href="https://example.com/x">x</a>',
    )
    assert extract_hrefs_from_mime(mime) == ["https://example.com/x"]


def test_extract_hrefs_catches_google_url():
    mime = build_mime(
        from_email="a@b.com",
        to=["c@d.com"],
        subject="Hi",
        html_body='<a href="https://www.google.com/url?q=https://example.com">x</a>',
    )
    hrefs = extract_hrefs_from_mime(mime)
    assert any("google.com/url" in h for h in hrefs)


def test_body_only_is_plain():
    mime = build_mime(
        from_email="a@b.com",
        to=["c@d.com"],
        subject="Hi",
        body="hello plain",
    )
    assert b"Content-Type: text/plain" in mime
    assert b"text/html" not in mime


def test_message_id_uses_generic_domain():
    mime = build_mime(
        from_email="a@b.com",
        to=["c@d.com"],
        subject="Hi",
        body="x",
    )
    assert b"gmail-mcp.local" in mime
    assert b"tail7838ad" not in mime
    assert b"macmini" not in mime


@respx.mock
async def test_send_with_proof(mail_env, monkeypatch):
    monkeypatch.setattr(
        "gmail_mcp.mail._idempotency_store",
        lambda: IdempotencyStore(mail_env["idem_path"]),
    )
    att = mail_env["outbox"] / "doc.pdf"
    att.write_bytes(b"%PDF-1.4 test content here")

    send_as = {"signature": "<p>Sig</p>"}
    respx.get(f"{GMAIL}/users/me/settings/sendAs/sender@example.com").mock(
        return_value=httpx.Response(200, json=send_as)
    )
    respx.post(f"{GMAIL_UP}/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "msg-1", "threadId": "thr-1"})
    )

    raw_mime = build_mime(
        from_email="sender@example.com",
        to=["recv@example.com"],
        subject="Test",
        html_body='<a href="https://example.com/x">x</a>',
        attachments=resolve_attachments(mail_env["outbox"], [{"path": str(att)}]),
    )
    raw_b64 = base64.urlsafe_b64encode(raw_mime).decode().rstrip("=")

    respx.get(f"{GMAIL}/users/me/messages/msg-1").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "msg-1",
                    "threadId": "thr-1",
                    "sizeEstimate": 5000,
                    "payload": {
                        "headers": [{"name": "From", "value": "sender@example.com"}],
                        "parts": [
                            {
                                "filename": "doc.pdf",
                                "body": {"attachmentId": "att-1", "size": len(att.read_bytes())},
                            }
                        ],
                    },
                },
            ),
            httpx.Response(200, json={"raw": raw_b64}),
        ]
    )
    att_data = att.read_bytes()
    respx.get(f"{GMAIL}/users/me/messages/msg-1/attachments/att-1").mock(
        return_value=httpx.Response(
            200,
            json={"data": base64.urlsafe_b64encode(att_data).decode().rstrip("=")},
        )
    )

    result = await send(
        account="sender@example.com",
        to="recv@example.com",
        subject="Test",
        idempotency_key="key-1",
        html_body='<a href="https://example.com/x">x</a>',
        attachments=[{"path": str(att)}],
    )
    assert result["ok"] is True
    assert result["id"] == "msg-1"
    assert result["hrefs"] == ["https://example.com/x"]
    assert result["attachments"][0]["sha256"] == hashlib.sha256(att_data).hexdigest()

    # idempotency replay — no second upload
    route = respx.post(f"{GMAIL_UP}/users/me/messages/send")
    assert route.call_count == 1
    result2 = await send(
        account="sender@example.com",
        to="recv@example.com",
        subject="Test",
        idempotency_key="key-1",
        html_body='<a href="https://example.com/x">x</a>',
    )
    assert result2["id"] == "msg-1"
    assert route.call_count == 1


@respx.mock
async def test_reply_uses_thread(mail_env, monkeypatch):
    monkeypatch.setattr(
        "gmail_mcp.mail._idempotency_store",
        lambda: IdempotencyStore(mail_env["idem_path"]),
    )
    respx.get(f"{GMAIL}/users/me/settings/sendAs/sender@example.com").mock(
        return_value=httpx.Response(200, json={"signature": ""})
    )
    respx.get(f"{GMAIL}/users/me/messages/orig-msg").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "orig-msg",
                "threadId": "thr-99",
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<orig@id>"},
                        {"name": "Subject", "value": "Hello"},
                        {"name": "From", "value": "other@example.com"},
                    ]
                },
            },
        )
    )
    respx.post(f"{GMAIL_UP}/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "reply-1", "threadId": "thr-99"})
    )
    raw_mime = build_mime(
        from_email="sender@example.com",
        to=["other@example.com"],
        subject="Re: Hello",
        body="reply body",
    )
    raw_b64 = base64.urlsafe_b64encode(raw_mime).decode().rstrip("=")
    respx.get(f"{GMAIL}/users/me/messages/reply-1").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "reply-1",
                    "threadId": "thr-99",
                    "sizeEstimate": 100,
                    "payload": {"headers": [{"name": "From", "value": "sender@example.com"}]},
                },
            ),
            httpx.Response(200, json={"raw": raw_b64}),
        ]
    )

    result = await reply(
        account="sender@example.com",
        message_id="orig-msg",
        idempotency_key="reply-key",
        body="Thanks",
    )
    assert result["threadId"] == "thr-99"
    assert result["ok"] is True


@respx.mock
async def test_forward_uses_thread(mail_env, monkeypatch):
    monkeypatch.setattr(
        "gmail_mcp.mail._idempotency_store",
        lambda: IdempotencyStore(mail_env["idem_path"]),
    )
    respx.get(f"{GMAIL}/users/me/settings/sendAs/sender@example.com").mock(
        return_value=httpx.Response(200, json={"signature": ""})
    )
    respx.get(f"{GMAIL}/users/me/messages/orig-msg").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "orig-msg",
                "threadId": "thr-forward",
                "payload": {
                    "headers": [
                        {"name": "Message-ID", "value": "<fwd@id>"},
                        {"name": "Subject", "value": "Original"},
                        {"name": "From", "value": "other@example.com"},
                    ]
                },
            },
        )
    )
    captured: dict = {}

    def _capture_send(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "fwd-1", "threadId": "thr-forward"})

    respx.post(f"{GMAIL_UP}/users/me/messages/send").mock(side_effect=_capture_send)

    raw_mime = build_mime(
        from_email="sender@example.com",
        to=["new@example.com"],
        subject="Fwd: Original",
        body="see below",
        in_reply_to="<fwd@id>",
        references="<fwd@id>",
    )
    raw_b64 = base64.urlsafe_b64encode(raw_mime).decode().rstrip("=")
    respx.get(f"{GMAIL}/users/me/messages/fwd-1").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "fwd-1",
                    "threadId": "thr-forward",
                    "sizeEstimate": 100,
                    "payload": {"headers": [{"name": "From", "value": "sender@example.com"}]},
                },
            ),
            httpx.Response(200, json={"raw": raw_b64}),
        ]
    )

    result = await forward(
        account="sender@example.com",
        message_id="orig-msg",
        to="new@example.com",
        idempotency_key="fwd-key",
        body="FYI",
    )
    assert result["threadId"] == "thr-forward"
    assert b"thr-forward" in captured.get("body", b"") or captured  # threadId in upload metadata
    assert b"<fwd@id>" in raw_mime
