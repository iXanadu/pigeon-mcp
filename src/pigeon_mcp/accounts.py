"""Account management — list, add (OAuth), remove."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from pigeon_mcp.config import settings
from pigeon_mcp.google_oauth import (
    build_auth_url,
    complete_oauth,
    ensure_fresh_token,
    revoke_and_remove,
    take_pending,
    web_client_credentials,
)
from pigeon_mcp.oauth_constants import STATUS_ACTIVE, STATUS_NEEDS_AUTH
from pigeon_mcp.token_store import TokenStore


@dataclass
class AccountSummary:
    account: str
    status: str

    def as_dict(self) -> dict[str, str]:
        return {"account": self.account, "status": self.status}


def _store() -> TokenStore:
    return TokenStore(settings.tokens_dir)


async def accounts_list() -> list[dict[str, str]]:
    """Connected Gmail addresses and whether each refresh token still works."""
    store = _store()
    summaries: list[AccountSummary] = []
    for email in store.list_emails():
        token = await ensure_fresh_token(store, email)
        if not token:
            summaries.append(AccountSummary(email, STATUS_NEEDS_AUTH))
            continue
        summaries.append(AccountSummary(email, token.status))
    return [s.as_dict() for s in summaries]


async def accounts_add() -> dict[str, str]:
    """Start Google OAuth, wait for browser consent, return the Gmail address."""
    from pigeon_mcp.oauth_callback import run_callback_server

    redirect_uri = settings.oauth_redirect_uri
    auth_url, state = build_auth_url(redirect_uri)
    print(f"Open this URL in a browser to connect Gmail:\n{auth_url}", file=sys.stderr)

    code = await run_callback_server(state, redirect_uri)
    if not code:
        raise TimeoutError(
            "OAuth consent timed out. Open the URL printed above and complete consent."
        )

    return await accounts_add_complete(code, state)


async def accounts_auth_start() -> dict[str, str]:
    """Begin Hand-initiated OAuth. Returns auth_url; complete via public /oauth/callback."""
    redirect_uri = settings.oauth_public_redirect_uri.strip()
    if not redirect_uri:
        raise RuntimeError(
            "PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI is required for Hand-initiated OAuth "
            "(set it to your public https://…/oauth/callback)"
        )
    client_id, client_secret = web_client_credentials()
    auth_url, state = build_auth_url(
        redirect_uri,
        client_id=client_id,
        client_secret=client_secret,
    )
    return {
        "auth_url": auth_url,
        "state": state,
        "redirect_uri": redirect_uri,
        "instructions": (
            "Open auth_url in a browser, sign in to Google, and allow access. "
            "Completion is automatic via the public redirect; then call accounts_list."
        ),
    }


async def accounts_add_complete(code: str, state: str) -> dict[str, str]:
    """Complete OAuth after Google redirects with code+state (stdio harness or HTTP callback)."""
    pending = take_pending(state)
    if not pending:
        raise ValueError("Invalid or expired OAuth state")
    token = await complete_oauth(
        code,
        pending.redirect_uri,
        _store(),
        client_id=pending.client_id,
        client_secret=pending.client_secret,
        code_verifier=pending.code_verifier,
    )
    return {"account": token.email, "status": token.status}


async def accounts_remove(account: str) -> dict[str, str]:
    """Drop local token; best-effort Google revoke (see revoke_and_remove)."""
    removed = await revoke_and_remove(_store(), account)
    if not removed:
        raise ValueError(f"Unknown account: {account}")
    return {"account": account, "removed": "true"}
