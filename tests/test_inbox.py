"""Tests for read/organise inbox tools."""

import base64
import httpx
import pytest
import respx

from pigeon_mcp.config import settings
from pigeon_mcp.inbox import (
    archive,
    draft_create,
    draft_send,
    get_attachment_file,
    get_message_detail,
    labels_list,
    search,
    trash,
)
from pigeon_mcp.oauth_constants import STATUS_ACTIVE
from pigeon_mcp.token_store import AccountToken, TokenStore

GMAIL = "https://gmail.googleapis.com/gmail/v1"


@pytest.fixture
def inbox_env(tmp_path, monkeypatch):
    outbox = tmp_path / "Outbox"
    outbox.mkdir()
    downloads = tmp_path / "Inbox"
    downloads.mkdir()
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    idem = tmp_path / "idempotency.json"
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "download_root", downloads)
    monkeypatch.setattr(settings, "tokens_dir", tokens)
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    store = TokenStore(tokens)
    store.save(
        AccountToken(
            email="user@example.com",
            refresh_token="rt",
            access_token="tok",
            expires_at="2099-01-01T00:00:00+00:00",
            status=STATUS_ACTIVE,
        )
    )
    return {"outbox": outbox, "downloads": downloads, "tokens": tokens, "idem_path": idem}


@respx.mock
async def test_search_returns_threads(inbox_env):
    respx.get(f"{GMAIL}/users/me/threads").mock(
        return_value=httpx.Response(
            200,
            json={
                "threads": [{"id": "t1", "snippet": "hello", "historyId": "123"}],
                "nextPageToken": "next",
            },
        )
    )
    result = await search("user@example.com", "in:inbox")
    assert len(result["threads"]) == 1
    assert result["threads"][0]["id"] == "t1"
    assert result["nextPageToken"] == "next"
    assert "messages" not in result


@respx.mock
async def test_get_attachment_writes_file(inbox_env):
    data = b"file-bytes"
    respx.get(f"{GMAIL}/users/me/messages/m1/attachments/a1").mock(
        return_value=httpx.Response(
            200,
            json={"data": base64.urlsafe_b64encode(data).decode().rstrip("=")},
        )
    )
    out = inbox_env["downloads"] / "saved.bin"
    result = await get_attachment_file("user@example.com", "m1", "a1", str(out))
    assert result["size"] == len(data)
    assert out.read_bytes() == data


def test_get_attachment_rejects_outside_download_root(inbox_env):
    from pigeon_mcp.attachments import resolve_download_path

    outside = inbox_env["downloads"].parent / "escape.bin"
    with pytest.raises(ValueError, match="download root"):
        resolve_download_path(inbox_env["downloads"], str(outside))


@respx.mock
async def test_labels_list(inbox_env):
    respx.get(f"{GMAIL}/users/me/labels").mock(
        return_value=httpx.Response(
            200,
            json={"labels": [{"id": "INBOX", "name": "INBOX", "type": "system"}]},
        )
    )
    result = await labels_list("user@example.com")
    assert result["labels"][0]["name"] == "INBOX"


@respx.mock
async def test_archive_removes_inbox(inbox_env):
    respx.post(f"{GMAIL}/users/me/threads/t1/modify").mock(
        return_value=httpx.Response(200, json={"id": "t1", "labelIds": ["UNREAD"]})
    )
    result = await archive("user@example.com", "t1")
    req = respx.calls.last.request
    assert b"INBOX" in req.content
    assert result["threadId"] == "t1"


@respx.mock
async def test_get_message_plain_body(inbox_env):
    body_b64 = base64.urlsafe_b64encode(b"plain text").decode().rstrip("=")
    respx.get(f"{GMAIL}/users/me/messages/m2").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "m2",
                "threadId": "t2",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [{"name": "Subject", "value": "S"}],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": body_b64},
                        }
                    ],
                },
            },
        )
    )
    result = await get_message_detail("user@example.com", "m2", format="plain")
    assert result["body"] == "plain text"


@respx.mock
async def test_draft_send_with_proof(inbox_env, monkeypatch):
    monkeypatch.setattr(
        "pigeon_mcp.inbox._idempotency_store",
        lambda: __import__("pigeon_mcp.idempotency", fromlist=["IdempotencyStore"]).IdempotencyStore(
            inbox_env["idem_path"]
        ),
    )
    respx.post(f"{GMAIL}/users/me/drafts/send").mock(
        return_value=httpx.Response(200, json={"id": "sent-1", "threadId": "t3"})
    )
    raw_mime = b"Subject: T\r\n\r\nplain"
    raw_b64 = base64.urlsafe_b64encode(raw_mime).decode().rstrip("=")
    respx.get(f"{GMAIL}/users/me/messages/sent-1").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "sent-1",
                    "threadId": "t3",
                    "sizeEstimate": 50,
                    "payload": {"headers": [{"name": "From", "value": "user@example.com"}]},
                },
            ),
            httpx.Response(200, json={"raw": raw_b64}),
        ]
    )
    result = await draft_send("user@example.com", "draft-1", "idem-1")
    assert result["ok"] is True
    assert result["id"] == "sent-1"
