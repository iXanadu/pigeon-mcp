"""HTTP bearer → tenant. Env token is seeded as grokbot; named tenants live in SQLite."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier

from pigeon_mcp.tenants import get_store, set_current_tenant


class TenantBearerVerifier:
    """Look up sha256(bearer) in the tenant drawer. Sets request-scoped tenant."""

    async def verify_token(self, token: str) -> AccessToken | None:
        set_current_tenant(None)
        tenant = get_store().resolve_bearer(token)
        if tenant is None:
            return None
        set_current_tenant(tenant)
        return AccessToken(token=token, client_id=tenant.name, scopes=[])


# Older tests / docs may still import this name.
StaticBearerVerifier = TenantBearerVerifier
