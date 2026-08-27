"""Tests for OAuth account management."""

import os
import stat

import httpx
import pytest
import respx
from unittest.mock import AsyncMock, patch

from gmail_mcp.accounts import (
    accounts_add,
    accounts_add_complete,
    accounts_auth_start,
    accounts_list,
    accounts_remove,
)
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


def test_token_file_mode_and_basename(token_store):
    token = AccountToken(
        email="alice@example.com",
        refresh_token="rt",
        access_token="at",
        status=STATUS_ACTIVE,
    )
    token_store.save(token)
    path = token_store.path_for("alice@example.com")
    assert path.name.startswith("gmail-token-")
    assert "token" in path.name
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o640
    dir_mode = stat.S_IMODE(os.stat(token_store.tokens_dir).st_mode)
    assert dir_mode == 0o750


def test_token_store_migrates_legacy_basename(token_store):
    legacy = token_store.tokens_dir / "bob_at_example.com.json"
    token_store.ensure_dir()
    legacy.write_text(
        '{"email":"bob@example.com","refresh_token":"rt","access_token":"at","status":"active"}\n',
        encoding="utf-8",
    )
    loaded = token_store.load("bob@example.com")
    assert loaded is not None
    assert loaded.email == "bob@example.com"
    token_store.save(loaded)
    assert token_store.path_for("bob@example.com").is_file()
    assert not legacy.is_file()


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
    token = await complete_oauth(
        "code-1",
        settings.oauth_redirect_uri,
        token_store,
        client_id="test-client-id",
        client_secret="test-client-secret",
        code_verifier="test-verifier",
    )
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
    route = respx.post("https://oauth2.googleapis.com/revoke").mock(
        return_value=httpx.Response(200, text="")
    )
    result = await accounts_remove("eve@gmail.com")
    assert result["removed"] == "true"
    assert token_store.load("eve@gmail.com") is None
    assert route.called
    assert route.calls.last.request.url.params["token"] == "rt"


@respx.mock
async def test_accounts_remove_revokes_refresh_when_access_missing(token_store):
    token_store.save(
        AccountToken(email="frank@gmail.com", refresh_token="rt-only", access_token="")
    )
    route = respx.post("https://oauth2.googleapis.com/revoke").mock(
        return_value=httpx.Response(200, text="")
    )
    result = await accounts_remove("frank@gmail.com")
    assert result["removed"] == "true"
    assert token_store.load("frank@gmail.com") is None
    assert route.called
    assert route.calls.last.request.url.params["token"] == "rt-only"


@respx.mock
async def test_accounts_remove_still_deletes_when_revoke_fails(token_store):
    token_store.save(
        AccountToken(email="gina@gmail.com", refresh_token="rt", access_token="at")
    )
    respx.post("https://oauth2.googleapis.com/revoke").mock(
        return_value=httpx.Response(503, text="unavailable")
    )
    result = await accounts_remove("gina@gmail.com")
    assert result["removed"] == "true"
    assert token_store.load("gina@gmail.com") is None


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
    assert "code_challenge=" in auth_url
    assert "code_challenge_method=S256" in auth_url
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


async def test_accounts_auth_start_returns_public_url(token_store, monkeypatch):
    monkeypatch.setattr(settings, "oauth_public_redirect_uri", "https://gmcp.example/oauth/callback")
    monkeypatch.setattr(settings, "google_web_client_id", "web-id")
    monkeypatch.setattr(settings, "google_web_client_secret", "web-secret")
    result = await accounts_auth_start()
    assert result["redirect_uri"] == "https://gmcp.example/oauth/callback"
    assert "accounts.google.com" in result["auth_url"]
    assert "code_challenge=" in result["auth_url"]
    assert result["state"]
