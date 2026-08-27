"""Account management — list, add (OAuth), remove."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from gmail_mcp.config import settings
from gmail_mcp.google_oauth import (
    build_auth_url,
    complete_oauth,
    ensure_fresh_token,
    revoke_and_remove,
    verify_state,
)
from gmail_mcp.oauth_constants import STATUS_ACTIVE, STATUS_NEEDS_AUTH
from gmail_mcp.token_store import TokenStore


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
    from gmail_mcp.oauth_callback import run_callback_server

    redirect_uri = settings.oauth_redirect_uri
    auth_url, state = build_auth_url(redirect_uri)
    print(f"Open this URL in a browser to connect Gmail:\n{auth_url}", file=sys.stderr)

    code = await run_callback_server(state, redirect_uri)
    if not code:
        raise TimeoutError(
            "OAuth consent timed out. Open the URL printed above and complete consent."
        )

    token = await complete_oauth(code, redirect_uri, _store())
    return {"account": token.email, "status": token.status}


async def accounts_add_complete(code: str, state: str) -> dict[str, str]:
    """Complete OAuth when the redirect code is captured manually (tests/harness)."""
    if not verify_state(state):
        raise ValueError("Invalid or expired OAuth state")
    token = await complete_oauth(code, settings.oauth_redirect_uri, _store())
    return {"account": token.email, "status": token.status}


async def accounts_remove(account: str) -> dict[str, str]:
    """Drop a connected account's token. Best-effort revoke at Google."""
    removed = await revoke_and_remove(_store(), account)
    if not removed:
        raise ValueError(f"Unknown account: {account}")
    return {"account": account, "removed": "true"}
