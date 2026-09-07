"""Request-scoped tenant (HTTP bearer) and grant checks."""

from __future__ import annotations

from contextvars import ContextVar

from pigeon_mcp.config import admin_db_path, settings
from pigeon_mcp.tenant_store import Tenant, TenantStore
from pigeon_mcp.token_store import TokenStore

_actor: ContextVar[Tenant | None] = ContextVar("pigeon_tenant", default=None)
_store: TenantStore | None = None
_store_path = ""


def get_store() -> TenantStore:
    global _store, _store_path
    path = str(admin_db_path())
    if _store is None or _store_path != path:
        if _store is not None:
            _store.close()
        _store = TenantStore(admin_db_path())
        _store_path = path
    _sync_legacy(_store)
    return _store


def reset_store_cache() -> None:
    global _store, _store_path
    if _store is not None:
        _store.close()
    _store = None
    _store_path = ""


def _sync_legacy(store: TenantStore) -> None:
    secret = (settings.http_bearer_token or "").strip()
    if not secret:
        return
    tid = store.upsert_env_bearer(secret, name="grokbot", can_auth_start=True)
    emails = TokenStore(settings.tokens_dir).list_emails()
    store.grant_all(tid, emails)


def set_current_tenant(tenant: Tenant | None) -> None:
    _actor.set(tenant)


def current_tenant() -> Tenant | None:
    return _actor.get()


def gate_http(tool: str, account: str = "", from_identity: str = "") -> None:
    """Stdio (no tenant): allow all. HTTP: grants + optional auth_start + audit."""
    tenant = current_tenant()
    if tenant is None:
        return
    if tool == "accounts_auth_start" and not tenant.can_auth_start:
        raise ValueError(
            f"Tenant {tenant.name!r} cannot connect mailboxes. An admin grants accounts."
        )
    if account and not tenant.allows(account):
        allowed = ", ".join(sorted(tenant.grants)) or "(none)"
        raise ValueError(
            f"Account {account} is not granted to tenant {tenant.name!r}. Allowed: {allowed}"
        )
    store = get_store()
    store.audit(
        tenant_name=tenant.name,
        tool=tool,
        account=account.lower() if account else "",
        from_identity=from_identity,
    )


def allowed_accounts() -> set[str] | None:
    """None means stdio / unrestricted. A set is the HTTP tenant's grants."""
    tenant = current_tenant()
    if tenant is None:
        return None
    return set(tenant.grants)
