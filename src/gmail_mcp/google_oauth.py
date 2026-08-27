"""Google OAuth refresh-token flow — adapted from beastchat/server/services/oauth.py."""

from __future__ import annotations

import secrets
import string
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx

from gmail_mcp.config import settings
from gmail_mcp.oauth_constants import (
    GMAIL_SCOPES,
    GOOGLE_AUTH_URL,
    GOOGLE_REVOKE_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    STATUS_ACTIVE,
    STATUS_NEEDS_AUTH,
)
from gmail_mcp.token_store import AccountToken, TokenStore

_STATE_TTL = timedelta(minutes=10)
_states: dict[str, datetime] = {}


def _gen_state() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def _gc_states() -> None:
    cutoff = datetime.now(timezone.utc) - _STATE_TTL
    stale = [k for k, v in _states.items() if v < cutoff]
    for k in stale:
        _states.pop(k, None)


def build_auth_url(redirect_uri: str) -> tuple[str, str]:
    """Return (auth_url, state). Caller must verify state on callback."""
    if not settings.google_client_id:
        raise RuntimeError("Google OAuth client_id not configured")
    state = _gen_state()
    _gc_states()
    _states[state] = datetime.now(timezone.utc)
    params = {
        "response_type": "code",
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "scope": GMAIL_SCOPES,
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}", state


def verify_state(state: str) -> bool:
    _gc_states()
    created = _states.pop(state, None)
    return created is not None


def _expires_at_from_response(body: dict) -> str | None:
    if not body.get("expires_in"):
        return None
    dt = datetime.now(timezone.utc) + timedelta(seconds=int(body["expires_in"]))
    return dt.isoformat()


async def exchange_code(code: str, redirect_uri: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(GOOGLE_TOKEN_URL, data=data)
        r.raise_for_status()
        return r.json()


async def fetch_user_email(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json().get("email", "")


async def refresh_access_token(store: TokenStore, email: str) -> AccountToken | None:
    """Refresh one account. On invalid_grant mark needs_auth; other accounts untouched."""
    token = store.load(email)
    if not token or not token.refresh_token:
        return None
    if token.status == STATUS_NEEDS_AUTH:
        return token

    data = {
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data=data)
            if r.status_code == 400 and "invalid_grant" in r.text:
                store.mark_needs_auth(email, "invalid_grant")
                refreshed = store.load(email)
                return refreshed
            r.raise_for_status()
            body = r.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400 and "invalid_grant" in exc.response.text:
            store.mark_needs_auth(email, "invalid_grant")
            return store.load(email)
        store.mark_needs_auth(email, str(exc)[:500])
        return store.load(email)
    except Exception as exc:
        store.mark_needs_auth(email, str(exc)[:500])
        return store.load(email)

    token.access_token = body.get("access_token", token.access_token)
    if body.get("refresh_token"):
        token.refresh_token = body["refresh_token"]
    token.expires_at = _expires_at_from_response(body)
    token.status = STATUS_ACTIVE
    token.last_error = ""
    store.save(token)
    return token


async def ensure_fresh_token(store: TokenStore, email: str) -> AccountToken | None:
    """Return token with valid access_token, refreshing if expiring within 2 minutes."""
    token = store.load(email)
    if not token:
        return None
    if token.status == STATUS_NEEDS_AUTH:
        return token

    remaining = TokenStore.expires_in_seconds(token.expires_at)
    if remaining is None or remaining <= 120:
        return await refresh_access_token(store, email)
    return token


async def complete_oauth(code: str, redirect_uri: str, store: TokenStore) -> AccountToken:
    body = await exchange_code(code, redirect_uri)
    access_token = body.get("access_token", "")
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        raise RuntimeError("Google did not return a refresh_token — revoke app access and retry with prompt=consent")

    email = await fetch_user_email(access_token)
    if not email:
        raise RuntimeError("Could not determine Gmail address from Google userinfo")

    token = AccountToken(
        email=email,
        refresh_token=refresh_token,
        access_token=access_token,
        expires_at=_expires_at_from_response(body),
        scopes=body.get("scope") or GMAIL_SCOPES,
        status=STATUS_ACTIVE,
    )
    store.save(token)
    return token


async def revoke_and_remove(store: TokenStore, email: str) -> bool:
    token = store.load(email)
    if not token:
        return False
    if token.access_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(GOOGLE_REVOKE_URL, params={"token": token.access_token})
        except Exception:
            pass
    store.delete(email)
    return True
