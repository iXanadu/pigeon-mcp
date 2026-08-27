"""Shared Gmail account session — access token for a connected account."""

from __future__ import annotations

from gmail_mcp.google_oauth import ensure_fresh_token
from gmail_mcp.oauth_constants import STATUS_NEEDS_AUTH
from gmail_mcp.token_store import TokenStore
from gmail_mcp.config import settings


def _token_store() -> TokenStore:
    return TokenStore(settings.tokens_dir)


async def access_token_for(account: str) -> str:
    store = _token_store()
    token = await ensure_fresh_token(store, account)
    if not token:
        raise ValueError(f"Unknown account: {account}")
    if token.status == STATUS_NEEDS_AUTH:
        raise ValueError(f"Account {account} needs re-consent (needs_auth)")
    if token.email.lower() != account.lower():
        raise ValueError(f"Account mismatch: expected {account}, have {token.email}")
    if not token.access_token:
        raise ValueError(f"No access token for {account}")
    return token.access_token
