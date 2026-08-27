"""Tests for OAuth account management."""

import os
import stat

import httpx
import pytest
import respx
from unittest.mock import AsyncMock, patch

from gmail_mcp.accounts import accounts_add, accounts_add_complete, accounts_list, accounts_remove
from gmail_mcp.config import settings
from gmail_mcp.google_oauth import build_auth_url, complete_oauth, refresh_access_token
from gmail_mcp.oauth_constants import STATUS_ACTIVE, STATUS_NEEDS_AUTH
from gmail_mcp.token_store import AccountToken, TokenStore

GMAIL_PROFILE = "https://gmail.googleapis.com/gmail/v1/users/me/profile"


@pytest.fixture
def token_store(tmp_path, monkeypatch):
    store_dir = tmp_path / "tokens"
    monkeypatch.setattr(settings, "tokens_dir", store_dir)
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "oauth_redirect_uri", "http://127.0.0.1:8767/oauth/callback")
    return TokenStore(store_dir)


def test_token_file_mode_0600(token_store):
    token = AccountToken(
        email="alice@example.com",
        refresh_token="rt",
        access_token="at",
        status=STATUS_ACTIVE,
    )
    token_store.save(token)
    mode = stat.S_IMODE(os.stat(token_store.path_for("alice@example.com")).st_mode)
    assert mode == 0o600
    dir_mode = stat.S_IMODE(os.stat(token_store.tokens_dir).st_mode)
    assert dir_mode == 0o700


@respx.mock
async def test_accounts_list_empty(token_store):
    rows = await accounts_list()
    assert rows == []


@respx.mock
async def test_accounts_list_needs_auth_without_refresh_token(token_store):
    token_store.save(
        AccountToken(email="ghost@example.com", refresh_token="", access_token="at")
    )
    rows = await accounts_list()
    assert rows == [{"account": "ghost@example.com", "status": STATUS_NEEDS_AUTH}]


@respx.mock
async def test_complete_oauth_saves_account(token_store):
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "scope": "gmail.modify gmail.send",
            },
        )
    )
    respx.get(GMAIL_PROFILE).mock(
        return_value=httpx.Response(200, json={"emailAddress": "bob@gmail.com"})
    )
    token = await complete_oauth("code-1", settings.oauth_redirect_uri, token_store)
    assert token.email == "bob@gmail.com"
    assert token.status == STATUS_ACTIVE
    loaded = token_store.load("bob@gmail.com")
    assert loaded is not None
    assert loaded.refresh_token == "refresh-1"


@respx.mock
async def test_refresh_invalid_grant_marks_needs_auth(token_store):
    token_store.save(
        AccountToken(
            email="carol@gmail.com",
            refresh_token="bad-refresh",
            access_token="old",
            status=STATUS_ACTIVE,
        )
    )
    token_store.save(
        AccountToken(
            email="dave@gmail.com",
            refresh_token="good-refresh",
            access_token="old2",
            status=STATUS_ACTIVE,
        )
    )
    respx.post("https://oauth2.googleapis.com/token").mock(
        side_effect=[
            httpx.Response(400, text='{"error":"invalid_grant"}'),
            httpx.Response(
                200,
                json={"access_token": "new-at", "expires_in": 3600},
            ),
        ]
    )
    carol = await refresh_access_token(token_store, "carol@gmail.com")
    dave = await refresh_access_token(token_store, "dave@gmail.com")
    assert carol is not None
    assert carol.status == STATUS_NEEDS_AUTH
    assert dave is not None
    assert dave.status == STATUS_ACTIVE
    assert dave.access_token == "new-at"


@respx.mock
async def test_accounts_remove(token_store):
    token_store.save(
        AccountToken(email="eve@gmail.com", refresh_token="rt", access_token="at")
    )
    respx.post("https://oauth2.googleapis.com/revoke").mock(
        return_value=httpx.Response(200, text="")
    )
    result = await accounts_remove("eve@gmail.com")
    assert result["removed"] == "true"
    assert token_store.load("eve@gmail.com") is None


@respx.mock
async def test_accounts_add_awaits_callback_and_returns_email(token_store, monkeypatch):
    monkeypatch.setattr(
        "gmail_mcp.oauth_callback.run_callback_server",
        AsyncMock(return_value="auth-code"),
    )
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access-3",
                "refresh_token": "refresh-3",
                "expires_in": 3600,
            },
        )
    )
    respx.get(GMAIL_PROFILE).mock(
        return_value=httpx.Response(200, json={"emailAddress": "grace@gmail.com"})
    )
    result = await accounts_add()
    assert result == {"account": "grace@gmail.com", "status": STATUS_ACTIVE}


@respx.mock
async def test_accounts_add_complete(token_store):
    auth_url, state = build_auth_url(settings.oauth_redirect_uri)
    assert "state=" in auth_url
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access-2",
                "refresh_token": "refresh-2",
                "expires_in": 3600,
            },
        )
    )
    respx.get(GMAIL_PROFILE).mock(
        return_value=httpx.Response(200, json={"emailAddress": "frank@gmail.com"})
    )
    result = await accounts_add_complete("auth-code", state)
    assert result["account"] == "frank@gmail.com"
    rows = await accounts_list()
    assert rows == [{"account": "frank@gmail.com", "status": STATUS_ACTIVE}]
