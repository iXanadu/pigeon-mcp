"""Tests for dispatch headers, metadata format, and messages_list."""

import base64

import httpx
import pytest
import respx

from pigeon_mcp.config import settings
from pigeon_mcp.gmail_client import DISPATCH_HEADERS
from pigeon_mcp.inbox import get_message_detail, get_thread_messages, messages_list
from pigeon_mcp.oauth_constants import STATUS_ACTIVE
from pigeon_mcp.token_store import AccountToken, TokenStore

GMAIL = "https://gmail.googleapis.com/gmail/v1"

HEADERS = [
    {"name": "From", "value": "Someone <someone@else.com>"},
    {"name": "To", "value": "engram@example.com"},
    {"name": "Subject", "value": "Hello"},
    {"name": "Delivered-To", "value": "mail@example.com"},
    {"name": "X-Gm-Original-To", "value": "engram@example.com"},
    {"name": "Reply-To", "value": "someone@else.com"},
    {"name": "Authentication-Results", "value": "mx.google.com; dkim=pass; dmarc=pass"},
    {"name": "Message-ID", "value": "<abc@else.com>"},
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    monkeypatch.setattr(settings, "tokens_dir", tokens)
    monkeypatch.setattr(settings, "google_client_id", "cid")
    monkeypatch.setattr(settings, "google_client_secret", "sec")
    TokenStore(tokens).save(
        AccountToken(
            email="mail@example.com",
            refresh_token="rt",
            access_token="tok",
            expires_at="2099-01-01T00:00:00+00:00",
            status=STATUS_ACTIVE,
        )
    )


@respx.mock
async def test_get_message_metadata_exposes_dispatch_headers(env):
    route = respx.get(f"{GMAIL}/users/me/messages/m1").mock(
        return_value=httpx.Response(
            200,
            json={"id": "m1", "threadId": "t1", "snippet": "hi", "payload": {"headers": HEADERS}},
        )
    )
    result = await get_message_detail("mail@example.com", "m1", format="metadata")
    assert result["deliveredTo"] == "mail@example.com"
    assert result["originalTo"] == "engram@example.com"
    assert result["replyTo"] == "someone@else.com"
    assert "dkim=pass" in result["authResults"]
    assert result["messageId"] == "<abc@else.com>"
    assert "body" not in result
    # metadata request asks Gmail for exactly the dispatch headers, no body
    url = str(route.calls[0].request.url)
    assert "format=metadata" in url
    for h in DISPATCH_HEADERS:
        assert f"metadataHeaders={h}" in url


@respx.mock
async def test_get_message_plain_still_fetches_full(env):
    body_b64 = base64.urlsafe_b64encode(b"text").decode().rstrip("=")
    route = respx.get(f"{GMAIL}/users/me/messages/m1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "m1",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": HEADERS,
                    "body": {"data": body_b64},
                },
            },
        )
    )
    result = await get_message_detail("mail@example.com", "m1", format="plain")
    assert result["body"] == "text"
    assert result["originalTo"] == "engram@example.com"
    assert "format=full" in str(route.calls[0].request.url)


@respx.mock
async def test_get_thread_metadata(env):
    route = respx.get(f"{GMAIL}/users/me/threads/t1").mock(
        return_value=httpx.Response(
            200,
            json={"id": "t1", "messages": [{"id": "m1", "threadId": "t1", "payload": {"headers": HEADERS}}]},
        )
    )
    result = await get_thread_messages("mail@example.com", "t1", format="metadata")
    assert result["messages"][0]["originalTo"] == "engram@example.com"
    assert "body" not in result["messages"][0]
    assert "format=metadata" in str(route.calls[0].request.url)


@respx.mock
async def test_messages_list_sweeps_metadata(env):
    respx.get(f"{GMAIL}/users/me/messages").mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "np"}
        )
    )
    respx.get(f"{GMAIL}/users/me/messages/m1").mock(
        return_value=httpx.Response(200, json={"id": "m1", "payload": {"headers": HEADERS}})
    )
    respx.get(f"{GMAIL}/users/me/messages/m2").mock(
        return_value=httpx.Response(
            200,
            json={"id": "m2", "payload": {"headers": [{"name": "To", "value": "mail@example.com"}]}},
        )
    )
    result = await messages_list("mail@example.com", "newer_than:1d", max_results=2)
    assert result["nextPageToken"] == "np"
    assert [m["id"] for m in result["messages"]] == ["m1", "m2"]
    assert result["messages"][0]["originalTo"] == "engram@example.com"
    # absent header = no rewrite happened; caller falls back to the mailbox itself
    assert result["messages"][1]["originalTo"] == ""
    assert "body" not in result["messages"][0]
