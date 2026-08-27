"""Account management — list, add (OAuth), remove."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from gmail_mcp.config import settings
from gmail_mcp.google_oauth import (
    build_auth_url,
    complete_oauth,
    ensure_fresh_token,
    revoke_and_remove,
    verify_state,
)
from gmail_mcp.oauth_constants import STATUS_ACTIVE
from gmail_mcp.token_store import TokenStore

_pending_flows: dict[str, asyncio.Task] = {}


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
    """Start Google OAuth consent. Opens browser to add a Gmail account."""
    redirect_uri = settings.oauth_redirect_uri
    auth_url, state = build_auth_url(redirect_uri)

    async def _wait_for_callback() -> None:
        from gmail_mcp.oauth_callback import run_callback_server

        code = await run_callback_server(state, redirect_uri)
        if code:
            await complete_oauth(code, redirect_uri, _store())

    task = asyncio.create_task(_wait_for_callback())
    _pending_flows[state] = task

    def _cleanup(t: asyncio.Task) -> None:
        _pending_flows.pop(state, None)

    task.add_done_callback(_cleanup)

    return {
        "auth_url": auth_url,
        "message": "Open auth_url in a browser. When consent completes, run accounts_list to verify.",
    }


async def accounts_add_complete(code: str, state: str) -> dict[str, str]:
    """Complete OAuth when the redirect code is captured manually."""
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
