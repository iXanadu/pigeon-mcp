"""Static bearer token verification for HTTP transport."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier


class StaticBearerVerifier:
    """Accept only the configured bearer token."""

    def __init__(self, expected_token: str) -> None:
        self.expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not self.expected_token or token != self.expected_token:
            return None
        return AccessToken(token=token, client_id="hand", scopes=[])
